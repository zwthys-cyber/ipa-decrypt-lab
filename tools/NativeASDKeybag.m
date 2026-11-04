// Account-free App Store daemon FairPlay prerequisite. Never imports or authorizes.
#define main KeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main
int main(int argc,const char **argv) { @autoreleasepool {
 if(argc!=2 || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-asd-keybag-v1",@"status":@"interface_unavailable",
   @"account_login_attempted":@NO,@"authorization_request_attempted":@NO,
   @"keybag_import_attempted":@NO,@"enrollment_created":@NO,@"decryption_proven":@NO} mutableCopy];
 @try {
   r[@"framework_loaded"]=B(dlopen("/System/Library/PrivateFrameworks/AppStoreDaemon.framework/AppStoreDaemon",RTLD_NOW|RTLD_GLOBAL)!=NULL);
   Class cls=NSClassFromString(@"ASDFairPlayService");SEL shared=NSSelectorFromString(@"defaultService");
   r[@"service_class_present"]=B(cls!=Nil);r[@"state_before"]=State();
   if(ABI(cls,shared,@"@",@[])) {
     id service=((id(*)(id,SEL))objc_msgSend)(cls,shared);
     SEL generate=NSSelectorFromString(@"generateKeybagRequestForDSID:error:");
     BOOL abi=ABI(service,generate,@"@",@[@"Q",@"^@"]);r[@"abi_verified"]=B(abi);
     if(abi) {
       NSError *error=nil;
       r[@"synthetic_request_attempted"]=@YES;
       id data=((id(*)(id,SEL,unsigned long long,NSError *__autoreleasing *))objc_msgSend)(service,generate,0,&error);
       ErrorFields(r,error);
       BOOL valid=[data isKindOfClass:NSData.class] && [data length]>0 && [data length]<=2097152;
       r[@"synthetic_sync_present"]=B(valid);
       r[@"status"]=valid && !error?@"synthetic_sync_ready":@"service_request_failed";
     }
   }
 } @catch(NSException *e) {r[@"status"]=@"native_exception";}
 r[@"state_after"]=State();
 NSData *out=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return out && [out writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
