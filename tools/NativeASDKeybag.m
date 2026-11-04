// Account-free App Store daemon FairPlay prerequisite. Never imports or authorizes.
#define main KeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main
static void ServiceErrorFields(NSMutableDictionary *r,NSError *error) {
 NSMutableString *text=[NSMutableString string];
 NSError *current=error;
 for(NSUInteger depth=0;depth<3 && current;depth++) {
   NSMutableArray *values=[NSMutableArray array];
   if(current.userInfo.count<=32)[values addObjectsFromArray:current.userInfo.allValues];
   if(current.localizedDescription)[values addObject:current.localizedDescription];
   if(current.localizedFailureReason)[values addObject:current.localizedFailureReason];
   for(id value in values)if([value isKindOfClass:NSString.class] && [value length]<=4096 && text.length<32768)
     [text appendFormat:@" %@ ",[value lowercaseString]];
   id next=current.userInfo[NSUnderlyingErrorKey];
   if(depth==0 && [next isKindOfClass:NSError.class]) {
     NSMutableDictionary *inner=[NSMutableDictionary dictionary];ErrorFields(inner,next);
     if(inner[@"error_domain"])r[@"underlying_error_domain"]=inner[@"error_domain"];
     if(inner[@"error_code"])r[@"underlying_error_code"]=inner[@"error_code"];
   }
   current=[next isKindOfClass:NSError.class] && next!=current?next:nil;
 }
 r[@"error_mentions_entitlement"]=B([text containsString:@"entitlement"] || [text containsString:@"not entitled"]);
 r[@"error_mentions_permission"]=B([text containsString:@"permission"] || [text containsString:@"not authorized"]);
 r[@"error_mentions_account"]=B([text containsString:@"account"] || [text containsString:@"dsid"]);
 r[@"error_mentions_connection"]=B([text containsString:@"connection"] || [text containsString:@"xpc"]);
}
static BOOL ServiceErrorContract(void) {
 NSError *inner=[NSError errorWithDomain:@"NSCocoaErrorDomain" code:4099 userInfo:@{NSLocalizedDescriptionKey:@"PRIVATE connection"}];
 NSError *error=[NSError errorWithDomain:@"ASDErrorDomain" code:505 userInfo:@{NSUnderlyingErrorKey:inner,
   @"ASDDebugDescription":@"PRIVATE entitlement permission dsid"}];
 NSMutableDictionary *r=[NSMutableDictionary dictionary];ServiceErrorFields(r,error);
 NSString *serialized=[[NSString alloc] initWithData:[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL] encoding:NSUTF8StringEncoding];
 return [r[@"underlying_error_domain"] isEqual:@"NSCocoaErrorDomain"] && [r[@"underlying_error_code"] isEqual:@4099]
   && [r[@"error_mentions_entitlement"] boolValue] && [r[@"error_mentions_permission"] boolValue]
   && [r[@"error_mentions_account"] boolValue] && [r[@"error_mentions_connection"] boolValue]
   && ![serialized containsString:@"PRIVATE"];
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(!getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 if(argc==2 && !strcmp(argv[1],"--error-contract")) {
   BOOL ok=ServiceErrorContract();puts(ok?"service error contract passed":"service error contract failed");return ok?0:4;
 }
 if(argc!=3 || (strcmp(argv[2],"zero") && strcmp(argv[2],"nonzero")))return 2;
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
       id data=((id(*)(id,SEL,unsigned long long,NSError *__autoreleasing *))objc_msgSend) (service,generate,!strcmp(argv[2],"zero")?0:1234567,&error);
       ErrorFields(r,error);ServiceErrorFields(r,error);
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
