#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#ifdef __APPLE__
#include <sys/mman.h>
#include <sys/wait.h>
#include <dlfcn.h>
#include <sys/utsname.h>
#include <signal.h>
#include <sys/sysctl.h>
#endif

#define IPA_LAB_MAX_INPUT (512U * 1024U * 1024U)
#define ARM64_CPU 0x0100000cU

typedef struct {
    uint32_t cpu, subtype, cryptoff, cryptsize, cryptid;
    size_t command_offset;
    int has_encryption;
} Image;

static uint32_t u32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
        ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void put32(unsigned char *p, uint32_t v) {
    for (unsigned i = 0; i < 4; i++) p[i] = (unsigned char)(v >> (8U * i));
}
static int fail(const char *s) {
    fprintf(stderr, "%s\n", s);
    return -1;
}
static int parse(const unsigned char *p, size_t n, Image *im) {
    memset(im, 0, sizeof(*im));
    if (n < 32) return fail("truncated Mach-O header");
    if (u32(p) != 0xfeedfacfU)
        return fail("unsupported format: requires thin little-endian 64-bit Mach-O; IPA/FAT must not be treated as thin binaries");
    im->cpu = u32(p + 4);
    im->subtype = u32(p + 8);
    uint32_t count = u32(p + 16), commands = u32(p + 20);
    if ((size_t)commands > n - 32 || count > commands / 8)
        return fail("invalid load command bounds");
    size_t off = 32, end = 32 + (size_t)commands;
    for (uint32_t i = 0; i < count; i++) {
        if (end - off < 8) return fail("truncated load command");
        uint32_t cmd = u32(p + off), size = u32(p + off + 4);
        if (size < 8 || (size % 8) != 0 || (size_t)size > end - off)
            return fail("invalid load command size/alignment");
        if (cmd == 0x21U) return fail("32-bit encryption command in 64-bit image");
        if (cmd == 0x2cU) {
            if (size != 24 || im->has_encryption)
                return fail("invalid or duplicate encryption command");
            im->has_encryption = 1;
            im->command_offset = off;
            im->cryptoff = u32(p + off + 8);
            im->cryptsize = u32(p + off + 12);
            im->cryptid = u32(p + off + 16);
            if ((size_t)im->cryptoff > n || (size_t)im->cryptsize > n - (size_t)im->cryptoff)
                return fail("encryption region outside file");
            if (im->cryptid && (!im->cryptsize || im->cryptoff < end))
                return fail("invalid encrypted region");
        }
        off += size;
    }
    if (off != end) return fail("load command length mismatch");
    return 0;
}
static unsigned char *load(const char *path, size_t *n) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) { perror("open input"); return NULL; }
    struct stat st;
    if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size < 0 ||
        (uint64_t)st.st_size > IPA_LAB_MAX_INPUT) {
        close(fd); fail("input must be a regular file, at most 512 MiB"); return NULL;
    }
    *n = (size_t)st.st_size;
    unsigned char *p = malloc(*n ? *n : 1);
    if (!p) { close(fd); return NULL; }
    size_t off = 0;
    while (off < *n) {
        ssize_t r = read(fd, p + off, *n - off);
        if (r < 0 && errno == EINTR) continue;
        if (r <= 0) { free(p); close(fd); fail("input read failed"); return NULL; }
        off += (size_t)r;
    }
    close(fd); return p;
}
#ifdef __APPLE__
typedef int (*RemapFn)(void *, size_t, uint32_t, uint32_t, uint32_t);

static int attempt(const char *input, const char *output, unsigned char *p, size_t n, const Image *im) {
    if (im->cpu != ARM64_CPU || !im->has_encryption || im->cryptid != 1U)
        return fail("native research backend requires an encrypted arm64 image with cryptid=1");
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || im->cryptoff % (uint32_t)page)
        return fail("encrypted start is not host-page aligned; backend unsupported");
    RemapFn remap = (RemapFn)dlsym(RTLD_DEFAULT, "mremap_encrypted");
    if (!remap) return fail("native FairPlay remap symbol unavailable");
    /* The system still requires valid account licenses and platform support.
       A symbol's existence is not proof the host can decrypt App Store apps. */
    int fd = open(input, O_RDONLY);
    if (fd < 0) return fail("cannot open mapping source");
    void *map = mmap(NULL, n, PROT_READ, MAP_PRIVATE, fd, 0);
    close(fd);
    if (map == MAP_FAILED) return fail("cannot map source image");
    unsigned char *region = (unsigned char *)map + im->cryptoff;
    /* XNU checks the start alignment and rounds the end internally. A final
       partial host page is valid; copy only the original cryptsize bytes. */
    puts("{\"event\":\"native_call\",\"requested_cryptid\":2}");
    fflush(stdout);
    errno = 0;
    int rc = remap(region, im->cryptsize, 2U, im->cpu, im->subtype);
    int call_errno = errno;
    printf("{\"event\":\"native_return\",\"return_code\":%d,\"errno\":%d}\n", rc, call_errno);
    fflush(stdout);
    if (rc != 0) {
        fprintf(stderr, "native backend refused request (errno=%d); license/platform may be unavailable\n", call_errno);
        munmap(map, n); return -1;
    }
    /* Reads can SIGBUS even after remap returned success. Caller isolates this
       operation in a child. Do not create output until all reads completed. */
    unsigned char *plain = malloc(im->cryptsize);
    if (!plain) { munmap(map, n); return -1; }
    memcpy(plain, region, im->cryptsize);
    munmap(map, n);
    if (!memcmp(plain, p + im->cryptoff, im->cryptsize)) {
        free(plain); return fail("mapped bytes unchanged; refusing a false decrypt");
    }
    memcpy(p + im->cryptoff, plain, im->cryptsize);
    free(plain);
    put32(p + im->command_offset + 16, 0);
    int out = open(output, O_CREAT | O_EXCL | O_WRONLY, 0600);
    if (out < 0) { perror("create candidate"); return -1; }
    size_t off = 0;
    while (off < n) {
        ssize_t wrote = write(out, p + off, n - off);
        if (wrote < 0 && errno == EINTR) continue;
        if (wrote <= 0) { close(out); unlink(output); return fail("candidate write failed"); }
        off += (size_t)wrote;
    }
    if (close(out)) { unlink(output); return fail("candidate close failed"); }
    puts("{\"status\":\"candidate_only\",\"runtime_verified\":false,\"warning\":\"changed bytes and cleared flag do not prove valid plaintext\"}");
    return 0;
}

/* Exercise the real system entry point with generated bytes and no account.
   Expected rejection is evidence only of this unlicensed synthetic case. */
static int native_selftest(uint32_t requested_cryptid) {
    long page = sysconf(_SC_PAGESIZE);
    if (page <= 0 || page > 65536) return 4;
    size_t size = (size_t)page * 2;
    unsigned char *sample = calloc(1, size);
    if (!sample) return 4;
    put32(sample, 0xfeedfacfU); put32(sample + 4, ARM64_CPU);
    put32(sample + 12, 2); put32(sample + 16, 1); put32(sample + 20, 24);
    put32(sample + 32, 0x2c); put32(sample + 36, 24);
    put32(sample + 40, (uint32_t)page); put32(sample + 44, (uint32_t)page);
    put32(sample + 48, 1);
    char scratch[] = "/tmp/ipa-lab-native-XXXXXX";
    int fd = mkstemp(scratch);
    if (fd < 0) { free(sample); return 4; }
    size_t off = 0;
    while (off < size) {
        ssize_t written = write(fd, sample + off, size - off);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) { close(fd); unlink(scratch); free(sample); return 4; }
        off += (size_t)written;
    }
    free(sample);
    int channel[2];
    if (pipe(channel)) { close(fd); unlink(scratch); return 4; }
    pid_t pid = fork();
    if (pid < 0) {
        close(channel[0]); close(channel[1]); close(fd); unlink(scratch); return 4;
    }
    if (!pid) {
        close(channel[0]);
        alarm(10);
        int report[4] = {0, -1, 0, 0};
        RemapFn remap = (RemapFn)dlsym(RTLD_DEFAULT, "mremap_encrypted");
        if (remap) {
            void *mapping = mmap(NULL, size, PROT_READ, MAP_PRIVATE, fd, 0);
            if (mapping != MAP_FAILED) {
                errno = 0;
                report[0] = 1;
                report[1] = remap((unsigned char *)mapping + page, (size_t)page, requested_cryptid, ARM64_CPU, 0);
                report[2] = errno;
                if (!report[1]) {
                    volatile unsigned char value = *((unsigned char *)mapping + page);
                    (void)value;
                    report[3] = 1;
                }
                munmap(mapping, size);
            }
        }
        (void)write(channel[1], report, sizeof(report));
        close(channel[1]); close(fd); _exit(0);
    }
    close(channel[1]); close(fd);
    int report[4] = {0, -1, 0, 0};
    size_t received = 0;
    while (received < sizeof(report)) {
        ssize_t got = read(channel[0], (unsigned char *)report + received, sizeof(report) - received);
        if (got < 0 && errno == EINTR) continue;
        if (got <= 0) break;
        received += (size_t)got;
    }
    close(channel[0]);
    int status = 0;
    pid_t waited;
    do { waited = waitpid(pid, &status, 0); } while (waited < 0 && errno == EINTR);
    unlink(scratch);
    if (waited < 0) return 4;
    printf("{\"sample\":\"synthetic_without_license\",\"cryptid\":%u,\"report_complete\":%s,"
           "\"native_call_attempted\":%s,\"return_code\":%d,\"errno\":%d,"
           "\"mapped_read_completed\":%s,\"signal\":%d,\"decryption_proven\":false}\n",
           requested_cryptid, received == sizeof(report) ? "true" : "false",
           report[0] ? "true" : "false", report[1], report[2],
           report[3] ? "true" : "false", WIFSIGNALED(status) ? WTERMSIG(status) : 0);
    return 0;
}
#endif
int main(int argc, char **argv) {
    if (argc == 2 && !strcmp(argv[1], "diagnose")) {
        for (uint32_t mode = 0; mode <= 2; mode++) {
#ifdef __APPLE__
            if (native_selftest(mode)) return 4;
#else
            printf("{\"sample\":\"synthetic_without_license\",\"cryptid\":%u,\"native_call_attempted\":false,\"reason\":\"unsupported_platform\",\"decryption_proven\":false}\n", mode);
#endif
        }
        return 0;
    }
    if (argc == 2 && !strcmp(argv[1], "self-test")) {
#ifdef __APPLE__
        return native_selftest(2U);
#else
        puts("{\"sample\":\"synthetic_without_license\",\"native_call_attempted\":false,\"reason\":\"unsupported_platform\",\"decryption_proven\":false}");
        return 0;
#endif
    }
    if (argc == 2 && !strcmp(argv[1], "probe")) {
#ifdef __APPLE__
        struct utsname os;
        if (uname(&os)) return 1;
        int virtualized = -1;
        size_t virtualized_size = sizeof(virtualized);
        if (sysctlbyname("kern.hv_vmm_present", &virtualized, &virtualized_size, NULL, 0)) virtualized = -1;
        printf("{\"platform\":\"macOS\",\"architecture\":\"%s\",\"page_size\":%ld,\"virtualized\":%d,\"native_symbol_available\":%s,\"account_authorization_verified\":false,\"decryption_proven\":false}\n",
            os.machine, sysconf(_SC_PAGESIZE), virtualized, dlsym(RTLD_DEFAULT, "mremap_encrypted") ? "true" : "false");
#else
        puts("{\"platform\":\"non-macOS\",\"native_symbol_available\":false,\"account_authorization_verified\":false,\"decryption_proven\":false}");
#endif
        return 0;
    }
    int inspect = argc == 3 && !strcmp(argv[1], "inspect");
    int decrypt = argc == 4 && !strcmp(argv[1], "attempt");
    if (!inspect && !decrypt) {
        fprintf(stderr, "Usage: ipa-engine probe | self-test | diagnose | inspect <Mach-O> | attempt <Mach-O> <candidate-output>\n");
        return 2;
    }
    size_t n = 0;
    unsigned char *p = load(argv[2], &n);
    if (!p) return 2;
    Image im;
    if (parse(p, n, &im)) { free(p); return 2; }
    if (inspect) {
        printf("{\"cpu_type\":%u,\"has_encryption_command\":%s,\"cryptid\":%u,\"encrypted_size\":%u,\"runtime_verified\":false}\n",
            im.cpu, im.has_encryption ? "true" : "false", im.cryptid, im.cryptsize);
        free(p); return 0;
    }
#ifdef __APPLE__
    pid_t child = fork();
    if (child < 0) { free(p); return 4; }
    if (!child) {
        alarm(30);
        int rc = attempt(argv[2], argv[3], p, n, &im);
        free(p); exit(rc ? 4 : 0);
    }
    free(p);
    int status = 0;
    pid_t waited;
    do { waited = waitpid(child, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited < 0) return 4;
    if (WIFSIGNALED(status)) {
        fprintf(stderr, "native backend terminated by signal %d; no valid decrypt established\n", WTERMSIG(status));
        return 4;
    }
    return WIFEXITED(status) ? WEXITSTATUS(status) : 4;
#else
    free(p);
    (void)put32;
    fail("native backend unavailable: requires a compatible Apple runtime; Linux build is inspection-only");
    return 4;
#endif
}
