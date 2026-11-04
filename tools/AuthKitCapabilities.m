// Account-free runtime metadata probe. Never instantiate an account or authenticate.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

static NSString *bounded(const char *value, size_t limit) {
    if (value == NULL || strnlen(value, limit + 1) > limit) return @"";
    return [NSString stringWithUTF8String:value] ?: @"";
}
static NSDictionary *methodInfo(Class cls, NSString *name) {
    Method method = cls ? class_getInstanceMethod(cls, NSSelectorFromString(name)) : NULL;
    return @{@"present": @(method != NULL),
             @"encoding": bounded(method ? method_getTypeEncoding(method) : NULL, 192)};
}
int main(void) {
    @autoreleasepool {
        const char *gha = getenv("GITHUB_ACTIONS");
        if (gha == NULL || strcmp(gha, "true") != 0) return 2;
        void *framework = dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit", RTLD_LAZY | RTLD_LOCAL);
        NSDictionary *queries = @{
            @"AKAppleIDAuthenticationContext": @[
                @"setAnisetteDataProvider:", @"anisetteDataProvider", @"setProxiedDeviceAnisetteData:",
                @"setCompanionDeviceAnisetteData:", @"setUsername:", @"_setPassword:",
                @"setShouldOfferSecurityUpgrade:", @"setShouldPreventInteractiveAuth:",
                @"setIsEphemeral:", @"setMaximumLoginAttempts:", @"setServiceType:",
                @"setShouldUpdatePersistentServiceTokens:"
            ],
            @"AKAnisetteData": @[@"setMachineID:", @"setOneTimePassword:", @"setRoutingInfo:"],
            @"AKAppleIDAuthenticationController": @[@"authenticateWithContext:completion:",
                @"updateStateWithExternalAuthenticationResponse:forContext:completion:"]
        };
        NSMutableDictionary *classes = [NSMutableDictionary dictionary];
        for (NSString *name in queries) {
            Class cls = NSClassFromString(name);
            NSMutableDictionary *methods = [NSMutableDictionary dictionary];
            for (NSString *selector in queries[name]) methods[selector] = methodInfo(cls, selector);
            classes[name] = @{@"present": @(cls != Nil), @"methods": methods};
        }
        Protocol *protocol = objc_getProtocol("AKAnisetteServiceProtocol");
        NSMutableArray *protocolMethods = [NSMutableArray array];
        BOOL limited = NO;
        for (int required = 0; required <= 1; required++) {
            for (int instance = 0; instance <= 1; instance++) {
                unsigned int count = 0;
                struct objc_method_description *list = protocol
                    ? protocol_copyMethodDescriptionList(protocol, required, instance, &count) : NULL;
                for (unsigned int i = 0; i < count; i++) {
                    if (protocolMethods.count >= 32) { limited = YES; break; }
                    [protocolMethods addObject:@{
                        @"selector": bounded(sel_getName(list[i].name), 160),
                        @"encoding": bounded(list[i].types, 192),
                        @"required": @(required == 1), @"instance": @(instance == 1)
                    }];
                }
                free(list);
            }
        }
#if defined(__arm64__)
        NSString *architecture = @"arm64";
#elif defined(__x86_64__)
        NSString *architecture = @"x86_64";
#else
        NSString *architecture = @"other";
#endif
        NSDictionary *report = @{
            @"schema": @"ipa-lab-authkit-capabilities-v1", @"architecture": architecture,
            @"framework_loaded": @(framework != NULL), @"classes": classes,
            @"protocol_present": @(protocol != NULL), @"protocol_methods": protocolMethods,
            @"protocol_method_limit_reached": @(limited),
            @"account_login_attempted": @NO, @"provider_installed": @NO,
            @"enrollment_created": @NO, @"decryption_proven": @NO
        };
        NSData *json = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:NULL];
        if (json == nil || json.length > 32768) return 2;
        fwrite(json.bytes, 1, json.length, stdout);
        fputc('\n', stdout);
        return framework ? 0 : 2;
    }
}
