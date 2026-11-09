#import <Foundation/Foundation.h>
#import <objc/message.h>
#import <dlfcn.h>
#import <unistd.h>
#import <sys/stat.h>
#include <string.h>

static NSDictionary *shape(id value) {
    BOOL string=[value isKindOfClass:NSString.class];
    BOOL data=[value isKindOfClass:NSData.class];
    NSUInteger length=(string || data) ? MIN([value length],256) : 0;
    BOOL hex=string && length==40 &&
        [value rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithCharactersInString:
        @"0123456789abcdefABCDEF"] invertedSet]].location==NSNotFound;
    BOOL hardware20=(data && length==20) || hex;
    return @{@"kind":string ? @"string" : data ? @"data" : value ? @"other" : @"absent",
             @"length":@(length),@"hardware20_shape":@(hardware20)};
}
static id getter(id target,NSString *name) {
    SEL selector=NSSelectorFromString(name);
    NSMethodSignature *signature=[target methodSignatureForSelector:selector];
    if(!signature || signature.numberOfArguments!=2 || signature.methodReturnType[0]!='@')return nil;
    return ((id(*)(id,SEL))objc_msgSend)(target,selector);
}
static NSDictionary *inspect(NSString *className,NSString *factory,NSString *name) {
    @try {
        Class cls=NSClassFromString(className);
        id target=factory.length ? getter(cls,factory) : cls;
        BOOL available=target && [target respondsToSelector:NSSelectorFromString(name)];
        return @{@"available":@(available),@"value":shape(available ? getter(target,name) : nil)};
    } @catch(NSException *exception) {
        return @{@"available":@NO,@"value":shape(nil)};
    }
}
int main(int argc,char **argv) {
    @autoreleasepool {
        umask(077);
        if(argc==2 && strcmp(argv[1],"--self-test")==0) {
            BOOL ok=[shape(@"00000000-0000-0000-0000-000000000000")[@"hardware20_shape"] isEqual:@NO] &&
                [shape(@"000102030405060708090a0b0c0d0e0f10111213")[@"hardware20_shape"] isEqual:@YES] &&
                [shape([NSMutableData dataWithLength:20])[@"hardware20_shape"] isEqual:@YES] &&
                [shape([NSMutableData dataWithLength:19])[@"hardware20_shape"] isEqual:@NO];
            return ok ? 0 : 2;
        }
        if(argc!=1)return 2;
        NSMutableDictionary *frameworks=[NSMutableDictionary dictionary];
        for(NSString *name in @[@"AuthKit",@"AppleMediaServices",@"StoreServices",@"TestFlightCore"]) {
            NSString *path=[NSString stringWithFormat:@"/System/Library/PrivateFrameworks/%@.framework/%@",name,name];
            BOOL loaded=dlopen(path.fileSystemRepresentation,RTLD_NOW|RTLD_LOCAL)!=NULL;
            frameworks[name]=@(loaded);
        }
        NSMutableDictionary *candidates=[NSMutableDictionary dictionary];
        candidates[@"authkit"] = inspect(@"AKDevice",@"currentDevice",@"uniqueDeviceIdentifier");
        candidates[@"store_services"] = inspect(@"SSDevice",@"currentDevice",@"uniqueDeviceIdentifier");
        for(NSString *selector in @[@"deviceGUID",@"deviceGUIDData",@"deviceIdentifier",
                                   @"uniqueDeviceIdentifier",@"deviceUDID"]) {
            candidates[selector]=inspect(@"AMSDevice",@"",selector);
        }
        NSDictionary *report=@{@"schema":@"testflight-native-discovery-v1",
            @"frameworks":frameworks,@"candidates":candidates,
            @"account_operation_attempted":@NO,@"raw_values_published":@NO};
        NSData *encoded=[NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingSortedKeys error:nil];
        if(!encoded || encoded.length>16384)return 2;
        write(STDOUT_FILENO,encoded.bytes,encoded.length);write(STDOUT_FILENO,"\n",1);
        return 0;
    }
}
