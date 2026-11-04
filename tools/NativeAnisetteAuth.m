// Private IPC adapter: only the Python worker may request device context or authentication.
#define main lab_contract_main
#include "AuthKitBridge.m"
#undef main

static BOOL enabled(const char *name) {
    const char *value = getenv(name);
    return value && strcmp(value, "1") == 0;
}
static id getObject(id object, NSString *selector) {
    return ((id (*)(id, SEL))objc_msgSend)(object, NSSelectorFromString(selector));
}
static NSDictionary *deviceContext(void) {
    Class cls = NSClassFromString(@"AKDevice");
    if (!cls || !class_getClassMethod(cls, NSSelectorFromString(@"currentDevice"))) return nil;
    id device = getObject((id)cls, @"currentDevice");
    NSMutableDictionary *values = [NSMutableDictionary dictionary];
    for (NSString *name in @[@"uniqueDeviceIdentifier", @"localUserUUID", @"serverFriendlyDescription"]) {
        if (!hasMethod(cls, name, 2)) return nil;
        id value = getObject(device, name);
        if (![value isKindOfClass:NSString.class] || [value length] == 0 || [value length] > 2048) return nil;
        values[name] = value;
    }
    return values;
}
static void emitLine(NSDictionary *value) {
    NSData *json = [NSJSONSerialization dataWithJSONObject:value options:NSJSONWritingSortedKeys error:NULL];
    if (!json || json.length > 32768) return;
    fwrite(json.bytes, 1, json.length, stdout);
    fputc('\n', stdout);
    fflush(stdout);
}
static id freshData(NSDictionary *device) {
    emitLine(@{@"request": @"anisette"});
    char bytes[32769];
    if (!fgets(bytes, sizeof(bytes), stdin) || !strchr(bytes, '\n')) return nil;
    NSData *raw = [NSData dataWithBytes:bytes length:strlen(bytes)];
    id value = [NSJSONSerialization JSONObjectWithData:raw options:0 error:NULL];
    if (![value isKindOfClass:NSDictionary.class] || ![value[@"device"] isEqual:device]) return nil;
    id headers = value[@"headers"];
    if (![headers isKindOfClass:NSDictionary.class]) return nil;
    for (NSString *name in @[@"X-Apple-I-MD", @"X-Apple-I-MD-M", @"X-Apple-I-MD-RINFO"]) {
        id item = headers[name];
        if (![item isKindOfClass:NSString.class] || [item length] == 0 || [item length] > 8192) return nil;
    }
    NSString *routing = headers[@"X-Apple-I-MD-RINFO"];
    if ([routing length] > 20 || [routing rangeOfCharacterFromSet:NSCharacterSet.decimalDigitCharacterSet.invertedSet].location != NSNotFound) return nil;
    Class cls = NSClassFromString(@"AKAnisetteData");
    if (!hasMethod(cls, @"setRoutingInfo:", 3)) return nil;
    id data = newObject(cls);
    setObject(data, @"setMachineID:", headers[@"X-Apple-I-MD-M"]);
    setObject(data, @"setOneTimePassword:", headers[@"X-Apple-I-MD"]);
    unsigned long long number = strtoull(routing.UTF8String, NULL, 10);
    ((void (*)(id, SEL, unsigned long long))objc_msgSend)(data, NSSelectorFromString(@"setRoutingInfo:"), number);
    return data;
}
static void setBool(id object, NSString *selector, BOOL value) {
    ((void (*)(id, SEL, BOOL))objc_msgSend)(object, NSSelectorFromString(selector), value);
}
static BOOL getBool(id object, NSString *selector) {
    return ((BOOL (*)(id, SEL))objc_msgSend)(object, NSSelectorFromString(selector));
}
static NSArray *privateErrorCodes(NSError *error) {
    NSSet *allowed = [NSSet setWithArray:@[@"AKAuthenticationError", @"AKAuthenticationServerError",
        @"AKAnisetteError", @"AKUnderlyingADIErrors", @"AKAttestationErrorDomain",
        @"com.apple.AppleIDAuthSupport", @"com.apple.devicecheck.error.baa",
        @"NSCocoaErrorDomain", @"NSPOSIXErrorDomain", @"NSURLErrorDomain", @"IPALab.Anisette"]];
    NSMutableArray *values = [NSMutableArray array];
    NSMutableArray *queue = error ? [NSMutableArray arrayWithObject:error] : [NSMutableArray array];
    NSUInteger examined = 0;
    while (queue.count && examined++ < 8) {
        NSError *item = queue.firstObject;
        [queue removeObjectAtIndex:0];
        if (![item isKindOfClass:NSError.class]) continue;
        if ([allowed containsObject:item.domain] && item.code >= -999999 && item.code <= 999999)
            [values addObject:@{@"domain": item.domain, @"code": @(item.code)}];
        id child = item.userInfo[NSUnderlyingErrorKey];
        if ([child isKindOfClass:NSError.class]) [queue addObject:child];
    }
    return values;
}
static BOOL resultHas(NSDictionary *result, const char *symbol, BOOL numericAllowed) {
    void *framework = dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit", RTLD_LAZY | RTLD_LOCAL);
    NSString *__unsafe_unretained *key = framework ? (NSString *__unsafe_unretained *)dlsym(framework, symbol) : NULL;
    if (!key || ![*key isKindOfClass:NSString.class]) return NO;
    id value = result[*key];
    return ([value isKindOfClass:NSString.class] && [value length] > 0) || (numericAllowed && [value isKindOfClass:NSNumber.class]);
}
static NSDictionary *authenticate(void) {
    NSMutableDictionary *report = [@{@"schema": @"ipa-lab-native-anisette-auth-v1",
        @"status": @"interface_unavailable", @"account_login_attempted": @NO,
        @"provider_fetch_calls": @0, @"provider_other_calls": @0,
        @"native_account_created": @NO, @"store_session_created": @NO,
        @"enrollment_created": @NO, @"decryption_proven": @NO} mutableCopy];
    if (!enabled("LAB_NATIVE_BRIDGE_AUTH")) { report[@"status"] = @"authentication_not_enabled"; return report; }
    NSDictionary *checks = contract();
    if (![checks[@"status"] isEqual:@"contract_verified"]) { report[@"status"] = @"contract_failed"; return report; }
    NSDictionary *device = deviceContext();
    if (!device) { report[@"status"] = @"device_context_unavailable"; return report; }
    NSDictionary *env = NSProcessInfo.processInfo.environment;
    NSString *username = env[@"APPLE_ID"];
    NSString *password = env[@"APPLE_PASSWORD"];
    if (!username.length || !password.length) { report[@"status"] = @"missing_credentials"; return report; }
    Class contextClass = NSClassFromString(@"AKAppleIDAuthenticationContext");
    Class controllerClass = NSClassFromString(@"AKAppleIDAuthenticationController");
    NSDictionary *policies = @{
        @"setShouldOfferSecurityUpgrade:": @"shouldOfferSecurityUpgrade",
        @"setShouldPreventInteractiveAuth:": @"shouldPreventInteractiveAuth",
        @"setIsEphemeral:": @"isEphemeral",
        @"setShouldUpdatePersistentServiceTokens:": @"shouldUpdatePersistentServiceTokens"
    };
    if (!hasMethod(controllerClass, @"authenticateWithContext:completion:", 4) ||
        !hasMethod(contextClass, @"setMaximumLoginAttempts:", 3) ||
        !hasMethod(contextClass, @"setUsername:", 3) || !hasMethod(contextClass, @"_setPassword:", 3)) return report;
    for (NSString *setter in policies) {
        if (!hasMethod(contextClass, setter, 3) || !hasMethod(contextClass, policies[setter], 2)) {
            report[@"status"] = @"context_policy_unavailable"; return report;
        }
    }
    id context = newObject(contextClass);
    setBool(context, @"setShouldOfferSecurityUpgrade:", NO);
    setBool(context, @"setShouldPreventInteractiveAuth:", YES);
    setBool(context, @"setIsEphemeral:", YES);
    setBool(context, @"setShouldUpdatePersistentServiceTokens:", NO);
    BOOL policy = !getBool(context, @"shouldOfferSecurityUpgrade") && getBool(context, @"shouldPreventInteractiveAuth") &&
        getBool(context, @"isEphemeral") && !getBool(context, @"shouldUpdatePersistentServiceTokens");
    report[@"context_policy_verified"] = @(policy);
    if (!policy) { report[@"status"] = @"context_policy_unavailable"; return report; }
    ((void (*)(id, SEL, long long))objc_msgSend)(context, NSSelectorFromString(@"setMaximumLoginAttempts:"), 1);
    setObject(context, @"setUsername:", username);
    setObject(context, @"_setPassword:", password);
    LabAnisetteProvider *provider = [LabAnisetteProvider new];
    __weak LabAnisetteProvider *weakProvider = provider;
    provider.dataSource = ^id {
        if (weakProvider.fetchCalls > 4) return nil;
        return freshData(device);
    };
    setObject(context, @"setAnisetteDataProvider:", provider);
    report[@"provider_retained_by_context"] = @((BOOL)(getObject(context, @"anisetteDataProvider") == provider));
    if (![report[@"provider_retained_by_context"] boolValue]) { report[@"status"] = @"contract_failed"; return report; }
    if (hasMethod(contextClass, @"serviceType", 2)) {
        long long serviceType = ((long long (*)(id, SEL))objc_msgSend)(context, NSSelectorFromString(@"serviceType"));
        if (serviceType >= 0 && serviceType <= 64) report[@"default_service_type"] = @(serviceType);
    }
    id controller = newObject(controllerClass);
    __block BOOL completed = NO;
    __block NSError *failure = nil;
    __block NSDictionary *answer = nil;
    void (^reply)(id, NSError *) = ^(id value, NSError *error) {
        @synchronized(report) {
            if ([value isKindOfClass:NSDictionary.class]) answer = value;
            failure = error;
            completed = YES;
        }
    };
    report[@"account_login_attempted"] = @YES;
    ((void (*)(id, SEL, id, id))objc_msgSend)(controller,
        NSSelectorFromString(@"authenticateWithContext:completion:"), context, reply);
    NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:45];
    BOOL done = NO;
    while (!done && deadline.timeIntervalSinceNow > 0) {
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
        @synchronized(report) { done = completed; }
    }
    @synchronized(report) {
        report[@"callback_completed"] = @(completed);
        report[@"errors"] = privateErrorCodes(failure);
        report[@"provider_fetch_calls"] = @(provider.fetchCalls);
        report[@"provider_other_calls"] = @(provider.otherCalls);
        report[@"result_dictionary_present"] = @((BOOL)(answer != nil));
        BOOL token = answer && resultHas(answer, "AKAuthenticationIDMSTokenKey", NO);
        BOOL identity = answer && (resultHas(answer, "AKAuthenticationDSIDKey", YES) ||
                                  resultHas(answer, "AKAuthenticationAlternateDSIDKey", YES));
        report[@"idms_token_present"] = @(token);
        report[@"account_identity_present"] = @(identity);
        report[@"status"] = !completed ? @"native_auth_timeout" : failure ? @"native_auth_rejected" :
            (token && identity) ? @"native_authentication_succeeded" : @"native_auth_result_unverified";
    }
    provider.dataSource = nil;
    return report;
}
int main(int argc, const char **argv) {
    @autoreleasepool {
        const char *gha = getenv("GITHUB_ACTIONS");
        if (!gha || strcmp(gha, "true") != 0 || !enabled("LAB_NATIVE_BRIDGE_PRIVATE_IPC") || argc != 2) return 2;
        NSDictionary *report = @{@"schema": @"ipa-lab-native-anisette-auth-v1", @"status": @"native_exception"};
        @try {
            if (!dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit", RTLD_LAZY | RTLD_LOCAL)) return 2;
            if (strcmp(argv[1], "--device-context") == 0) {
                NSDictionary *device = deviceContext();
                if (!device) return 2;
                emitLine(device); // Private pipe to the worker only; never a workflow entry point.
                return 0;
            }
            if (strcmp(argv[1], "--authenticate") != 0) return 2;
            report = authenticate();
        } @catch (NSException *exception) { }
        emitLine(report);
        return [report[@"status"] isEqual:@"native_authentication_succeeded"] ? 0 : 2;
    }
}
