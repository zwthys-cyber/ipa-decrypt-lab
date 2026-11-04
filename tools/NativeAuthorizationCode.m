// Load only public system frameworks in our own account-free research process.
#import <Foundation/Foundation.h>
#import <dlfcn.h>
#import <objc/runtime.h>
void *lab_store_token_impl;
void *lab_dictionary_token_impl;
#include <stdlib.h>
#include <string.h>
__attribute__((noinline)) void lab_frameworks_loaded(void) { __asm__ volatile("" ::: "memory"); }
int main(void) { @autoreleasepool {
 const char *ci=getenv("GITHUB_ACTIONS");
 if(!ci || strcmp(ci,"true"))return 2;
 if(!dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL))return 3;
 if(!dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL))return 4;
 Method storeMethod=class_getInstanceMethod(NSClassFromString(@"ACAccountStore"),NSSelectorFromString(@"ams_secureTokenForAccount:"));
 Method dictionaryMethod=class_getInstanceMethod(NSDictionary.class,NSSelectorFromString(@"ams_secureToken"));
 lab_store_token_impl=storeMethod?(void *)method_getImplementation(storeMethod):NULL;
 lab_dictionary_token_impl=dictionaryMethod?(void *)method_getImplementation(dictionaryMethod):NULL;
 lab_frameworks_loaded();
 return 0;
}}
