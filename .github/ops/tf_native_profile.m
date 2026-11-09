#import <Foundation/Foundation.h>
#import <objc/message.h>
#import <objc/runtime.h>
#import <dlfcn.h>
#import <sys/sysctl.h>
#import <sys/stat.h>
#import <fcntl.h>
#import <unistd.h>
#import <string.h>
#import <stdio.h>
#import "LabStoreBagTransport.h"

static void stage(const char *name) { dprintf(STDERR_FILENO,"TF_PROBE_STAGE:%s\n",name); }
static id object0(id target, NSString *name) {
    SEL selector=NSSelectorFromString(name);
    if(!target || ![target respondsToSelector:selector])return nil;
    return ((id(*)(id,SEL))objc_msgSend)(target,selector);
}
static BOOL safe(NSString *value,NSUInteger limit) {
    return [value isKindOfClass:NSString.class] && value.length>0 && value.length<=limit &&
           [value rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location==NSNotFound;
}
static NSString *hex20(id value) {
    if([value isKindOfClass:NSData.class] && [value length]==20) {
        const unsigned char *bytes=[value bytes];
        NSMutableString *result=[NSMutableString string];
        for(NSUInteger i=0;i<20;i++)[result appendFormat:@"%02x",bytes[i]];
        return result;
    }
    if([value isKindOfClass:NSString.class] && [value length]==40 &&
       [value rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:@"0123456789abcdefABCDEF"] invertedSet]].location==NSNotFound)return [value lowercaseString];
    return nil;
}
static NSDictionary *profile(NSMutableDictionary *report) {
    stage("started");
    dlopen("/System/Library/PrivateFrameworks/AuthKit.framework/AuthKit",RTLD_NOW|RTLD_LOCAL);
    id device=object0(NSClassFromString(@"AKDevice"),@"currentDevice");
    stage("identity");
    id raw=object0(device,@"uniqueDeviceIdentifier");
    NSString *identity=hex20(raw);
    report[@"native_identifier_length"]=@([raw isKindOfClass:NSString.class] ? MIN([raw length],128) : 0);
    report[@"native_udid_20"]=@(identity!=nil);
    report[@"hardware_source"]=identity ? @"authkit_unique_identifier" : @"unavailable";
    stage("model");
    char modelBuffer[256]={0};size_t length=sizeof(modelBuffer);
    NSString *model=nil;
    if(sysctlbyname("hw.model",modelBuffer,&length,NULL,0)==0)
        model=[[NSString alloc] initWithBytes:modelBuffer length:strnlen(modelBuffer,sizeof(modelBuffer)) encoding:NSUTF8StringEncoding];
    BOOL modelValid=safe(model,128) && [model rangeOfString:@"Mac" options:NSCaseInsensitiveSearch].location!=NSNotFound;
    report[@"native_mac_model"]=@(modelValid);
    stage("bag");
    id bag=[LabStoreBagTransport nativeBag];
    stage("headers");
    Class anisette=NSClassFromString(@"AMSAnisette");
    SEL headersSelector=NSSelectorFromString(@"headersForRequest:account:type:bag:");
    id headers=nil;
    if(bag && [anisette respondsToSelector:headersSelector]) {
        id pending=((id(*)(id,SEL,id,id,long long,id))objc_msgSend)(anisette,headersSelector,
            [NSURLRequest requestWithURL:[NSURL URLWithString:@"https://auth.itunes.apple.com/auth/v1/native"]],nil,2,bag);
        SEL wait=NSSelectorFromString(@"resultWithError:");
        headers=[pending respondsToSelector:wait] ? ((id(*)(id,SEL,NSError **))objc_msgSend)(pending,wait,NULL) : pending;
    }
    NSString *machine=[headers isKindOfClass:NSDictionary.class] ? headers[@"X-Apple-AMD-M"] : nil;
    BOOL machineValid=safe(machine,8192);
    report[@"native_machine_header"]=@(machineValid);
    if(!identity || !modelValid || !machineValid)return nil;
    NSOperatingSystemVersion version=NSProcessInfo.processInfo.operatingSystemVersion;
    NSString *agent=[NSString stringWithFormat:@"IPADecryptLab-TestFlight/0.1 (macOS %ld.%ld.%ld)",version.majorVersion,version.minorVersion,version.patchVersion];
    return @{@"schema":@"testflight-native-profile-v1",@"udid":identity,
             @"hardware_source":@"authkit_unique_identifier",@"deviceName":@"CI TestFlight worker",
             @"headers":@{@"User-Agent":agent,@"X-Apple-Device-Model":model,@"X-Apple-TA-Device":model,
                           @"X-Apple-TestFlight-iOS":@"0",@"X-Apple-Rosetta-Available":@"0",@"X-Apple-AMD-M":machine}};
}
static BOOL writePrivate(NSDictionary *value,NSString *path) {
    NSString *base=NSProcessInfo.processInfo.environment[@"RUNNER_TEMP"];
    NSString *parent=path.stringByDeletingLastPathComponent.stringByStandardizingPath;
    if(!safe(base,4096) || ![parent hasPrefix:[base.stringByStandardizingPath stringByAppendingString:@"/"]])return NO;
    struct stat info;
    if(lstat(parent.fileSystemRepresentation,&info)!=0 || !S_ISDIR(info.st_mode) ||
       (info.st_mode&077)!=0 || info.st_uid!=getuid())return NO;
    NSData *data=[NSJSONSerialization dataWithJSONObject:value options:0 error:nil];
    if(!data || data.length>32768)return NO;
    int file=open(path.fileSystemRepresentation,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if(file<0)return NO;
    BOOL ok=write(file,data.bytes,data.length)==(ssize_t)data.length;
    close(file);if(!ok)unlink(path.fileSystemRepresentation);
    return ok;
}
int main(int argc,char **argv) {
    @autoreleasepool {
        umask(077);
        NSMutableDictionary *report=[@{@"schema":@"testflight-native-preflight-v1",@"status":@"unavailable",
            @"native_udid_20":@NO,@"native_mac_model":@NO,@"native_machine_header":@NO,
            @"native_identifier_length":@0,@"hardware_source":@"unavailable",@"private_profile_written":@NO} mutableCopy];
        BOOL ok=NO;
        @try {
            NSDictionary *value=profile(report);
            ok=value!=nil;
            if(ok && argc==3 && strcmp(argv[1],"--output")==0) {
                ok=writePrivate(value,[NSString stringWithUTF8String:argv[2]]);
                report[@"private_profile_written"]=@(ok);
            } else if(argc!=1)ok=NO;
            report[@"status"]=ok ? @"ready" : @"native_context_unavailable";
        } @catch(NSException *exception) { report[@"status"]=@"native_probe_stopped";ok=NO; }
        stage("finished");
        NSData *data=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:nil];
        if(data)write(STDOUT_FILENO,data.bytes,data.length);
        write(STDOUT_FILENO,"\n",1);
        return ok ? 0 : 2;
    }
}
