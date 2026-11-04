// Account-free AuthKit daemon transport check. No authentication selector is called.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <dlfcn.h>
#include <string.h>

static BOOL method(Class cls, NSString *name, unsigned int count) {
    Method m = cls ? class_getInstanceMethod(cls, NSSelectorFromString(name)) : NULL;
    return m && method_getNumberOfArguments(m) == count;
}
static NSDictionary *errorReport(NSError *error) {
    NSMutableDictionary *r = [@{@"error_present": @((BOOL)(error != nil)),
        @"xpc_connection_invalid": @NO, @"xpc_connection_interrupted": @NO} mutableCopy];
    r[@"sdk_xpc_invalid_code"] = @(NSXPCConnectionInvalid);
    if ([error.domain isEqual:NSCocoaErrorDomain]) {
        r[@"xpc_connection_invalid"] = @(error.code == NSXPCConnectionInvalid);
        r[@"xpc_connection_interrupted"] = @(error.code == NSXPCConnectionInterrupted);
    }
    NSSet *domains = [NSSet setWithArray:@[@"NSCocoaErrorDomain", @"AKAuthenticationError",
        @"AKAuthenticationServerError", @"NSPOSIXErrorDomain", @"NSURLErrorDomain"]];
    if ([domains containsObject:error.domain] && error.code >= -999999 && error.code <= 999999) {
        r[@"error_domain"] = error.domain;
        r[@"error_code"] = @(error.code);
    }
    NSMutableString *text = [NSMutableString string];
    for (id item in @[error.localizedDescription ?: @"", error.userInfo[NSDebugDescriptionErrorKey] ?: @""]) {
        if ([item isKindOfClass:NSString.class] && [item length] <= 8192) [text appendString:[item lowercaseString]];
    }
    NSDictionary *phrases = @{
        @"missing_entitlement": @[@"missing entitlement", @"not entitled", @"lacks entitlement", @"does not have the entitlement"],
        @"code_signing_requirement": @[@"code signing", @"codesigning", @"code-signing"],
        @"lookup_failed": @[@"failed at lookup"],
        @"service_missing": @[@"no such process", @"service not found"],
        @"connection_invalidated": @[@"invalidated"],
        @"sandbox_denied": @[@"sandbox restriction", @"sandbox denied"],
        @"connection_rejected": @[@"connection rejected", @"connection was rejected"],
    };
    for (NSString *key in phrases) {
        BOOL found = NO;
        for (NSString *phrase in phrases[key]) if ([text containsString:phrase]) found = YES;
        r[key] = @(found);
    }
    return r;
}
int main(int argc, const char **argv) {
    @autoreleasepool {
        if (!getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"), "true") || argc != 2) return 2;
        if (getenv("APPLE_ID") || getenv("APPLE_PASSWORD")) return 2;
        BOOL named = strcmp(argv[1], "named") == 0;
        if (!named && strcmp(argv[1], "default")) return 2;
        NSMutableDictionary *r = [@{@"schema": @"ipa-lab-authkit-transport-v1",
            @"status": @"interface_unavailable", @"explicit_client_identifier": @(named),
            @"bundle_identifier_present": @((BOOL)(NSBundle.mainBundle.bundleIdentifier.length > 0)),
            @"account_login_attempted": @NO, @"enrollment_created": @NO, @"decryption_proven": @NO} mutableCopy];
        @try {
            dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit", RTLD_LAZY | RTLD_LOCAL);
            Class cls = NSClassFromString(@"AKAppleIDAuthenticationController");
            NSString *selector = method(cls, @"fetchURLBagWithCompletion:", 3) ? @"fetchURLBagWithCompletion:" :
                method(cls, @"fetchURLBagForAltDSID:completion:", 4) ? @"fetchURLBagForAltDSID:completion:" : nil;
            r[@"bag_selector_present"] = @((BOOL)(selector != nil));
            r[@"identifier_initializer_present"] = @(method(cls, @"initWithIdentifier:", 3));
            id controller = nil;
            if (cls && selector && (!named || method(cls, @"initWithIdentifier:", 3))) {
                id object = ((id (*)(id, SEL))objc_msgSend)((id)cls, @selector(alloc));
                controller = named ? ((id (*)(id, SEL, id))objc_msgSend)(object,
                    NSSelectorFromString(@"initWithIdentifier:"), @"org.ipa-lab.AuthKitTransport") :
                    ((id (*)(id, SEL))objc_msgSend)(object, @selector(init));
            }
            if (controller) {
                __block BOOL completed = NO;
                __block BOOL bagPresent = NO;
                __block NSError *failure = nil;
                void (^reply)(id, NSError *) = ^(id bag, NSError *error) {
                    @synchronized(r) {
                        bagPresent = bag != nil;
                        failure = error;
                        completed = YES;
                    }
                };
                if ([selector isEqual:@"fetchURLBagWithCompletion:"])
                    ((void (*)(id, SEL, id))objc_msgSend)(controller, NSSelectorFromString(selector), reply);
                else
                    ((void (*)(id, SEL, id, id))objc_msgSend)(controller, NSSelectorFromString(selector), nil, reply);
                NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:15];
                BOOL done = NO;
                while (!done && deadline.timeIntervalSinceNow > 0) {
                    [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
                    @synchronized(r) { done = completed; }
                }
                @synchronized(r) {
                    [r addEntriesFromDictionary:errorReport(failure)];
                    r[@"callback_completed"] = @(completed);
                    r[@"bag_result_present"] = @(bagPresent);
                    r[@"status"] = !completed ? @"transport_timeout" : failure ? @"transport_rejected" :
                        bagPresent ? @"bag_fetch_succeeded" : @"empty_result";
                }
            }
        } @catch (NSException *exception) { r[@"status"] = @"native_exception"; }
        NSData *json = [NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingSortedKeys error:NULL];
        fwrite(json.bytes, 1, json.length, stdout);
        fputc('\n', stdout);
        return 0;
    }
}
