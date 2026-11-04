// Load only public system frameworks in our own account-free research process.
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#include <stdlib.h>
#include <string.h>
__attribute__((noinline)) void lab_frameworks_loaded(void) { __asm__ volatile("" ::: "memory"); }
int main(void) { @autoreleasepool {
 const char *ci=getenv("GITHUB_ACTIONS");
 if(!ci || strcmp(ci,"true"))return 2;
 if(!dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL))return 3;
 if(!dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL))return 4;
 lab_frameworks_loaded();
 return 0;
}}
