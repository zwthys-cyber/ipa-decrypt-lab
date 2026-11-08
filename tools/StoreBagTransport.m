#import "LabStoreBagTransport.h"
#import <objc/runtime.h>
#import <objc/message.h>
#import <dlfcn.h>

static IMP originalBagRequest;
static id createBagRequest(id task,SEL selector,id queryItems) {
    id pending=((id(*)(id,SEL,id))originalBagRequest)(task,selector,queryItems);
    id request=pending;
    SEL wait=NSSelectorFromString(@"resultWithError:");
    BOOL promise=[pending respondsToSelector:wait];
    if(promise)request=((id(*)(id,SEL,NSError **))objc_msgSend)(pending,wait,NULL);
    if(![request isKindOfClass:NSURLRequest.class])return pending;
    NSURLRequest *updated=[LabStoreBagTransport publicRequest:request];
    if(updated==request)return pending;
    if(promise)return ((id(*)(id,SEL,id))objc_msgSend)(NSClassFromString(@"AMSPromise"),NSSelectorFromString(@"promiseWithResult:"),updated);
    return updated;
}

__attribute__((constructor)) static void initializeStoreTransport(void) {
    @autoreleasepool { [LabStoreBagTransport nativeBag]; }
}

@implementation LabStoreBagTransport
+ (id)nativeBag {
    if(![self install])return nil;
    static dispatch_once_t once;
    static id bag=nil;
    dispatch_once(&once, ^{
        Class cls=NSClassFromString(@"AMSAnisette");
        SEL selector=NSSelectorFromString(@"createBagForSubProfile");
        if([cls respondsToSelector:selector])bag=((id(*)(id,SEL))objc_msgSend)(cls,selector);
    });
    return bag;
}
+ (BOOL)install {
    static dispatch_once_t once;
    static BOOL installed=NO;
    dispatch_once(&once, ^{
        if(!dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_LOCAL))return;
        Method method=class_getInstanceMethod(NSClassFromString(@"AMSBagNetworkTask"),NSSelectorFromString(@"_createRequestWithQueryItems:"));
        if(!method||method_getNumberOfArguments(method)!=3)return;
        originalBagRequest=method_setImplementation(method,(IMP)createBagRequest);
        installed=YES;
    });
    return installed;
}
+ (NSURLRequest *)publicRequest:(NSURLRequest *)request {
    NSURLComponents *p=[NSURLComponents componentsWithURL:request.URL resolvingAgainstBaseURL:NO];
    if(![p.scheme isEqual:@"https"]||![@[@"bag.itunes.apple.com",@"init.itunes.apple.com"] containsObject:p.host]||
       ![p.percentEncodedPath isEqual:@"/bag.xml"]||p.user||p.password||p.fragment||(p.port&&p.port.integerValue!=443)||![request.HTTPMethod isEqual:@"GET"])return request;
    // Retain NSURLProtocol properties used by the native AMS session encoder.
    NSMutableURLRequest *updated=[request mutableCopy];
    updated.URL=[NSURL URLWithString:@"https://init.itunes.apple.com/bag.xml?ix=6"];
    for(NSString *field in @[@"Cookie",@"Authorization",@"X-Token",@"X-Dsid",@"iCloud-DSID",@"X-Apple-AMD",@"X-Apple-AMD-M",@"X-Apple-ActionSignature"]) {
        [updated setValue:nil forHTTPHeaderField:field];
    }
    updated.HTTPBody=nil;
    updated.timeoutInterval=20;
    // Public configuration only. Never carry account headers across origins.
    updated.HTTPMethod=@"GET";
    [updated setValue:@"Configurator/2.21 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6" forHTTPHeaderField:@"User-Agent"];
    return updated;
}
@end
