// Linked only into our diagnostic executable. Never injected into system processes.
#include "NativeImportIO.h"
// SDKs do not ship dyld-interposing.h. Emit the documented dyld tuple ABI.
// Reference: apple-oss-distributions/dyld/include/mach-o/dyld-interposing.h.
// These workflows build arm64 and x86_64, not the arm64e pointer-auth variant.
#if defined(__arm64e__)
#error Unsupported pointer-authenticated interpose ABI
#endif
#define LAB_INTERPOSE(hook,target) \
 __attribute__((used,section("__DATA,__interpose"))) \
 static const struct { const void *replacement; const void *original; } \
 lab_tuple_##target = { (const void *)&hook, (const void *)&target };

#include <stdatomic.h>
#include <pthread.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/file.h>
#include <sys/param.h>

enum { OP_OPEN, OP_OPENAT, OP_FOPEN, OP_STAT, OP_LSTAT, OP_ACCESS, OP_MKDIR,
 OP_UNLINK, OP_RENAME, OP_READ, OP_WRITE, OP_PREAD, OP_PWRITE, OP_FSYNC,
 OP_FCLOSE, OP_FREAD, OP_FWRITE, OP_FLOCK, OP_FTRUNCATE };
static const char *names[LAB_IO_OPS]={"open","openat","fopen","stat","lstat","access",
 "mkdir","unlink","rename","read","write","pread","pwrite","fsync","fclose",
 "fread","fwrite","flock","ftruncate"};
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static _Atomic unsigned int epoch;
static unsigned int serial;
static LabIOSnapshot state;
const char *LabImportIOOperation(unsigned int index){return index<LAB_IO_OPS?names[index]:"unknown";}
void LabImportIOBegin(void) {
 int saved=errno;pthread_mutex_lock(&lock);
 atomic_store(&epoch,0);memset(&state,0,sizeof(state));
 if(++serial==0)serial=1;atomic_store(&epoch,serial);
 pthread_mutex_unlock(&lock);errno=saved;
}
void LabImportIOEnd(LabIOSnapshot *snapshot) {
 int saved=errno;pthread_mutex_lock(&lock);
 atomic_store(&epoch,0);if(snapshot)*snapshot=state;
 pthread_mutex_unlock(&lock);errno=saved;
}
static int under(const char *path,const char *root) {
 size_t n=strlen(root);return !strncmp(path,root,n) && (!path[n] || path[n]=='/');
}
static int area_path(const char *path) {
 if(!path || strnlen(path,MAXPATHLEN)==MAXPATHLEN || strstr(path,"/../") || strstr(path,"/./"))return -1;
 size_t n=strlen(path);
 if((n>=3 && !strcmp(path+n-3,"/..")) || (n>=2 && !strcmp(path+n-2,"/.")))return -1;
 if(under(path,"/Users/Shared/SC Info"))return 0;
 if(under(path,"/private/var/db/fpsd/SC Info") || under(path,"/var/db/fpsd/SC Info"))return 1;
 return -1;
}
static int area_fd(int fd) {
 int saved=errno;char path[MAXPATHLEN];
 int result=fcntl(fd,F_GETPATH,path)==0?area_path(path):-1;errno=saved;return result;
}
static int area_at(int fd,const char *path) {
 if(!path || path[0]=='/')return area_path(path);
 int saved=errno;char base[MAXPATHLEN],full[MAXPATHLEN];int result=-1;
 if(fd==AT_FDCWD?getcwd(base,sizeof(base))!=NULL:fcntl(fd,F_GETPATH,base)==0) {
   int n=snprintf(full,sizeof(full),"%s/%s",base,path);
   if(n>0 && n<(int)sizeof(full))result=area_path(full);
 }
 errno=saved;return result;
}
static void increment(uint32_t *counter) {
 if(*counter<LAB_IO_LIMIT)(*counter)++;else state.capped=1;
}
static void record(unsigned int generation,int area,int op,int failed,int error) {
 if(!generation || area<0 || area>=LAB_IO_AREAS)return;
 pthread_mutex_lock(&lock);
 if(atomic_load(&epoch)==generation) {
   LabIOCell *cell=&state.cells[area][op];increment(&cell->calls);
   if(failed) {
     increment(&cell->failures);cell->last_errno=error>=0 && error<=255?(uint32_t)error:256;
     if(error==EACCES || error==EPERM)increment(&cell->permission_failures);
     if(error==ENOENT)increment(&cell->missing_failures);
   }
 }
 pthread_mutex_unlock(&lock);
}
static int traced_open(const char *path,int flags,...) {
 mode_t mode=0;if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);}
 unsigned int g=atomic_load(&epoch);int result=open(path,flags,mode),saved=errno;
 if(g)record(g,area_path(path),OP_OPEN,result<0,saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_open,open)
static int traced_openat(int fd,const char *path,int flags,...) {
 mode_t mode=0;if(flags&O_CREAT){va_list ap;va_start(ap,flags);mode=va_arg(ap,int);va_end(ap);}
 unsigned int g=atomic_load(&epoch);int a=g?area_at(fd,path):-1;
 int result=openat(fd,path,flags,mode),saved=errno;
 record(g,a,OP_OPENAT,result<0,saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_openat,openat)
static FILE *traced_fopen(const char *path,const char *mode) {
 unsigned int g=atomic_load(&epoch);FILE *result=fopen(path,mode);int saved=errno;
 if(g)record(g,area_path(path),OP_FOPEN,!result,saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_fopen,fopen)
#define PATH_HOOK(name,op,args,call) \
 static int traced_##name args { \
  unsigned int g=atomic_load(&epoch);int result=name call,saved=errno; \
  if(g)record(g,area_path(path),op,result<0,saved);errno=saved;return result; \
 } \
 LAB_INTERPOSE(traced_##name,name)
PATH_HOOK(stat,OP_STAT,(const char *path,struct stat *st),(path,st))
PATH_HOOK(lstat,OP_LSTAT,(const char *path,struct stat *st),(path,st))
PATH_HOOK(access,OP_ACCESS,(const char *path,int mode),(path,mode))
PATH_HOOK(mkdir,OP_MKDIR,(const char *path,mode_t mode),(path,mode))
PATH_HOOK(unlink,OP_UNLINK,(const char *path),(path))
static int traced_rename(const char *from,const char *to) {
 unsigned int g=atomic_load(&epoch);int result=rename(from,to),saved=errno;
 if(g){int a=area_path(to);record(g,a>=0?a:area_path(from),OP_RENAME,result<0,saved);}
 errno=saved;return result;
}
LAB_INTERPOSE(traced_rename,rename)
#define FD_HOOK(type,name,op,args,call) \
 static type traced_##name args { \
  unsigned int g=atomic_load(&epoch);int a=g?area_fd(fd):-1; \
  type result=name call;int saved=errno;record(g,a,op,result<0,saved);errno=saved;return result; \
 } \
 LAB_INTERPOSE(traced_##name,name)
FD_HOOK(ssize_t,read,OP_READ,(int fd,void *buffer,size_t size),(fd,buffer,size))
FD_HOOK(ssize_t,write,OP_WRITE,(int fd,const void *buffer,size_t size),(fd,buffer,size))
FD_HOOK(ssize_t,pread,OP_PREAD,(int fd,void *buffer,size_t size,off_t offset),(fd,buffer,size,offset))
FD_HOOK(ssize_t,pwrite,OP_PWRITE,(int fd,const void *buffer,size_t size,off_t offset),(fd,buffer,size,offset))
FD_HOOK(int,fsync,OP_FSYNC,(int fd),(fd))
FD_HOOK(int,flock,OP_FLOCK,(int fd,int operation),(fd,operation))
FD_HOOK(int,ftruncate,OP_FTRUNCATE,(int fd,off_t size),(fd,size))
static int traced_fclose(FILE *stream) {
 unsigned int g=atomic_load(&epoch);int a=g?area_fd(fileno(stream)):-1;
 int result=fclose(stream),saved=errno;record(g,a,OP_FCLOSE,result!=0,saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_fclose,fclose)
static size_t traced_fread(void *buffer,size_t size,size_t count,FILE *stream) {
 unsigned int g=atomic_load(&epoch);int a=g?area_fd(fileno(stream)):-1;
 size_t result=fread(buffer,size,count,stream);int saved=errno;
 record(g,a,OP_FREAD,result<count && ferror(stream),saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_fread,fread)
static size_t traced_fwrite(const void *buffer,size_t size,size_t count,FILE *stream) {
 unsigned int g=atomic_load(&epoch);int a=g?area_fd(fileno(stream)):-1;
 size_t result=fwrite(buffer,size,count,stream);int saved=errno;
 record(g,a,OP_FWRITE,result<count && ferror(stream),saved);errno=saved;return result;
}
LAB_INTERPOSE(traced_fwrite,fwrite)
