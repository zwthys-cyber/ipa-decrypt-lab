// Account-free bridge contract. Synthetic values never reach an authentication endpoint.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>
#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

static NSString *bounded(const char *value, size_t limit) {
    if (!value || strnlen(value, limit + 1) > limit) return @"";
    return [NSString stringWithUTF8String:value] ?: @"";
}
static BOOL hasMethod(Class cls, NSString *name, unsigned int arguments) {
    Method method = cls ? class_getInstanceMethod(cls, NSSelectorFromString(name)) : NULL;
    return method && method_getNumberOfArguments(method) == arguments;
}
static id newObject(Class cls) {
    return ((id (*)(id, SEL))objc_msgSend)((id)cls, @selector(new));
}
static void setObject(id object, NSString *name, id value) {
    ((void (*)(id, SEL, id))objc_msgSend)(object, NSSelectorFromString(name), value);
}
@interface LabAnisetteProvider : NSObject
@property(nonatomic, strong) id data;
@property(nonatomic, copy) id (^dataSource)(void);
@property(nonatomic) NSUInteger fetchCalls;
@property(nonatomic) NSUInteger otherCalls;
@end
@implementation LabAnisetteProvider
- (void)fetchAnisetteDataAndProvisionIfNecessary:(BOOL)needed withCompletion:(void (^)(id, NSError *))completion {
    id value = nil;
    @synchronized(self) {
        self.fetchCalls++;
        value = self.dataSource ? self.dataSource() : self.data;
    }
    completion(value, value ? nil : [NSError errorWithDomain:@"IPALab.Anisette" code:1 userInfo:nil]);
}
- (void)legacyAnisetteDataForDSID:(id)dsid withCompletion:(void (^)(id, NSError *))completion {
    self.otherCalls++;
    completion(nil, [NSError errorWithDomain:@"IPALab.Anisette" code:2 userInfo:nil]);
}
- (void)provisionAnisetteWithCompletion:(void (^)(BOOL, NSError *))completion {
    self.otherCalls++;
    completion(NO, [NSError errorWithDomain:@"IPALab.Anisette" code:2 userInfo:nil]);
}
- (void)eraseAnisetteWithCompletion:(void (^)(BOOL, NSError *))completion {
    self.otherCalls++;
    completion(NO, [NSError errorWithDomain:@"IPALab.Anisette" code:2 userInfo:nil]);
}
- (void)syncAnisetteWithSIMData:(id)data completion:(void (^)(BOOL, NSError *))completion {
    self.otherCalls++;
    completion(NO, [NSError errorWithDomain:@"IPALab.Anisette" code:2 userInfo:nil]);
}
- (void)fetchPeerAttestationDataForRequest:(id)request completion:(void (^)(id, NSError *))completion {
    self.otherCalls++;
    completion(nil, [NSError errorWithDomain:@"IPALab.Anisette" code:2 userInfo:nil]);
}
@end

static NSDictionary *contract(void) {
    NSMutableDictionary *report = [@{@"status": @"interface_unavailable",
        @"provider_retained_by_context": @NO, @"native_proxy_callback_verified": @NO,
        @"missing_data_rejected": @NO, @"fetch_calls": @0, @"other_calls": @0} mutableCopy];
    Class contextClass = NSClassFromString(@"AKAppleIDAuthenticationContext");
    Class proxyClass = NSClassFromString(@"_AKAnisetteProviderProxy");
    Class dataClass = NSClassFromString(@"AKAnisetteData");
    report[@"proxy_class_present"] = @((BOOL)(proxyClass != Nil));
    objc_property_t property = contextClass ? class_getProperty(contextClass, "anisetteDataProvider") : NULL;
    report[@"provider_property_attributes"] = bounded(property ? property_getAttributes(property) : NULL, 256);
    NSMutableArray *names = [NSMutableArray array];
    unsigned int count = 0;
    Protocol *__unsafe_unretained *protocols = objc_copyProtocolList(&count);
    for (unsigned int i = 0; i < count && names.count < 16; i++) {
        NSString *name = bounded(protocol_getName(protocols[i]), 160);
        if ([name containsString:@"Anisette"]) [names addObject:name];
    }
    free(protocols);
    report[@"registered_anisette_protocols"] = [names sortedArrayUsingSelector:@selector(compare:)];
    NSString *fetch = @"fetchAnisetteDataForContext:provisionIfNecessary:withCompletion:";
    if (!hasMethod(contextClass, @"setAnisetteDataProvider:", 3) ||
        !hasMethod(contextClass, @"anisetteDataProvider", 2) ||
        !hasMethod(proxyClass, @"initWithProvider:", 3) || !hasMethod(proxyClass, fetch, 5) ||
        !hasMethod(dataClass, @"setMachineID:", 3) || !hasMethod(dataClass, @"setOneTimePassword:", 3)) return report;
    report[@"proxy_fetch_encoding"] = bounded(method_getTypeEncoding(
        class_getInstanceMethod(proxyClass, NSSelectorFromString(fetch))), 192);
    id data = newObject(dataClass);
    setObject(data, @"setMachineID:", @"c3ludGhldGljLW1hY2hpbmU=");
    setObject(data, @"setOneTimePassword:", @"c3ludGhldGljLW90cA==");
    LabAnisetteProvider *provider = [LabAnisetteProvider new];
    provider.data = data;
    id context = newObject(contextClass);
    setObject(context, @"setAnisetteDataProvider:", provider);
    id returned = ((id (*)(id, SEL))objc_msgSend)(context, NSSelectorFromString(@"anisetteDataProvider"));
    report[@"provider_retained_by_context"] = @((BOOL)(returned == provider));
    id allocated = ((id (*)(id, SEL))objc_msgSend)((id)proxyClass, @selector(alloc));
    id proxy = ((id (*)(id, SEL, id))objc_msgSend)(allocated, NSSelectorFromString(@"initWithProvider:"), provider);
    __block BOOL completed = NO;
    __block BOOL matched = NO;
    void (^reply)(id, NSError *) = ^(id result, NSError *error) {
        matched = (result == data && error == nil);
        completed = YES;
    };
    ((void (*)(id, SEL, id, BOOL, id))objc_msgSend)(proxy, NSSelectorFromString(fetch), context, NO, reply);
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:2];
    while (!completed && deadline.timeIntervalSinceNow > 0)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    report[@"native_proxy_callback_verified"] = @((BOOL)(completed && matched && provider.fetchCalls == 1));
    provider.data = nil;
    completed = NO;
    __block BOOL rejected = NO;
    void (^negativeReply)(id, NSError *) = ^(id result, NSError *error) {
        rejected = (result == nil && error != nil);
        completed = YES;
    };
    ((void (*)(id, SEL, id, BOOL, id))objc_msgSend)(proxy, NSSelectorFromString(fetch), context, NO, negativeReply);
    deadline = [NSDate dateWithTimeIntervalSinceNow:2];
    while (!completed && deadline.timeIntervalSinceNow > 0)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    report[@"missing_data_rejected"] = @((BOOL)(completed && rejected));
    report[@"fetch_calls"] = @(provider.fetchCalls);
    report[@"other_calls"] = @(provider.otherCalls);
    BOOL passed = [report[@"provider_retained_by_context"] boolValue] &&
        [report[@"native_proxy_callback_verified"] boolValue] &&
        [report[@"missing_data_rejected"] boolValue] && provider.fetchCalls == 2 && provider.otherCalls == 0;
    report[@"status"] = passed ? @"contract_verified" : @"contract_failed";
    return report;
}
int main(int argc, const char **argv) {
    @autoreleasepool {
        const char *gha = getenv("GITHUB_ACTIONS");
        if (!gha || strcmp(gha, "true") != 0 || argc != 2 || strcmp(argv[1], "--self-test") != 0) return 2;
        NSMutableDictionary *report = [@{@"schema": @"ipa-lab-authkit-bridge-v1",
            @"status": @"framework_unavailable"} mutableCopy];
        @try {
            void *framework = dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit", RTLD_LAZY | RTLD_LOCAL);
            if (framework) [report addEntriesFromDictionary:contract()];
        } @catch (NSException *exception) {
            report[@"status"] = @"native_exception";
        }
        report[@"account_login_attempted"] = @NO;
        report[@"native_account_created"] = @NO;
        report[@"enrollment_created"] = @NO;
        report[@"decryption_proven"] = @NO;
        NSData *json = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:NULL];
        if (!json || json.length > 8192) return 2;
        fwrite(json.bytes, 1, json.length, stdout);
        fputc('\n', stdout);
        return [report[@"status"] isEqual:@"contract_verified"] ? 0 : 2;
    }
}
