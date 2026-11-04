// Account-free local CommerceKit request generation. Never authorizes or imports.
#define main KeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main
#include <signal.h>
#include <unistd.h>
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

static void Deadline(int value) {(void)value;_exit(124);}
static void LoaderFields(NSMutableDictionary *r,const char *message) {
 NSString *text=message?[@(message) lowercaseString]:@"";
 r[@"loader_mentions_missing"]=B([text containsString:@"not found"] || [text containsString:@"no such file"]);
 r[@"loader_mentions_architecture"]=B([text containsString:@"architecture"] || [text containsString:@"incompatible"]);
 r[@"loader_mentions_signature"]=B([text containsString:@"code signature"] || [text containsString:@"library validation"]);
}
static id SyntheticAccount(BOOL nonzero,NSMutableDictionary *r) {
 Class clientClass=NSClassFromString(@"CKStoreClient"),accountClass=NSClassFromString(@"CKStoreAccount");
 r[@"client_class_present"]=B(clientClass!=Nil);r[@"account_class_present"]=B(accountClass!=Nil);
 id client=[clientClass alloc];SEL initClient=NSSelectorFromString(@"initWithClientIdentifier:");
 if(!ABI(client,initClient,@"@",@[@"@"]))return nil;
 client=((id(*)(id,SEL,id))objc_msgSend)(client,initClient,@"com.apple.AppStore");
 id account=[accountClass alloc];SEL initAccount=NSSelectorFromString(@"_initWithStoreClient:plist:");
 if(!client || !ABI(account,initAccount,@"@",@[@"@",@"@"]))return nil;
 NSNumber *expected=nonzero?@1234567:@0;
 account=((id(*)(id,SEL,id,id))objc_msgSend)(account,initAccount,client,@{@"dsPersonID":expected,@"appleId":@"ipa-lab@example.invalid"});
 SEL dsid=NSSelectorFromString(@"dsID");
 if(!ABI(account,dsid,@"@",@[]))return nil;
 id observed=((id(*)(id,SEL))objc_msgSend)(account,dsid);
 BOOL verified=[observed isKindOfClass:NSNumber.class] && [observed isEqual:expected];
 r[@"synthetic_account_verified"]=B(verified);
 return verified?account:nil;
}
static void CommerceRequest(BOOL nonzero,NSMutableDictionary *r) {
 dlerror();
 BOOL loaded=dlopen("/System/Library/PrivateFrameworks/CommerceKit.framework/CommerceKit",RTLD_NOW|RTLD_GLOBAL)!=NULL;
 const char *loaderError=loaded?NULL:dlerror();
 r[@"framework_loaded"]=B(loaded);LoaderFields(r,loaderError);
 if(!loaded){r[@"status"]=@"framework_unavailable";return;}
 Class cls=NSClassFromString(@"ServiceProxy");
 r[@"service_class_present"]=B(cls!=Nil);
 SEL get=NSSelectorFromString(@"commerceServiceWithErrorHandler:");
 if(!ABI(cls,get,@"@",@[@"@?"]))return;
 id account=SyntheticAccount(nonzero,r);
 if(!account){r[@"status"]=@"synthetic_account_unavailable";return;}
 NSLock *lock=[NSLock new];dispatch_semaphore_t done=dispatch_semaphore_create(0);
 __block BOOL finished=NO;
 void (^finish)(BOOL,BOOL,id,BOOL,id)=^(BOOL transport,BOOL success,id data,BOOL needDiv,id suppliedError) {
   [lock lock];
   if(!finished) {
     finished=YES;
     BOOL errorValid=!suppliedError || [suppliedError isKindOfClass:NSError.class];
     NSError *error=errorValid?suppliedError:nil;
     r[@"reply_received"]=B(!transport);r[@"transport_error_received"]=B(transport);
     r[@"service_success"]=B(success);r[@"need_diversitybag"]=B(needDiv);
     BOOL present=[data isKindOfClass:NSData.class] && [data length]>0 && [data length]<=2097152;
     r[@"synthetic_sync_present"]=B(present);
     ErrorFields(r,error);ServiceErrorFields(r,error);
     r[@"status"]=!errorValid?@"malformed_service_reply":
       !transport && success && present && !error?@"synthetic_sync_ready":@"service_request_failed";
     dispatch_semaphore_signal(done);
   }
   [lock unlock];
 };
 id service=((id(*)(id,SEL,id))objc_msgSend)(cls,get,^(NSError *error){finish(YES,NO,nil,NO,error);});
 SEL generate=NSSelectorFromString(@"kbSyncForTransactionType:account:reply:");
 BOOL valid=ABI(service,generate,@"v",@[@"C",@"@",@"@?"]) || ABI(service,generate,@"v",@[@"c",@"@",@"@?"]);
 r[@"abi_verified"]=B(valid);
 if(!valid)return;
 r[@"synthetic_request_attempted"]=@YES;
 // The four-argument reply is verified from the actual Intel macOS callback descriptor.
 ((void(*)(id,SEL,unsigned char,id,id))objc_msgSend)(service,generate,2,account,
   ^(char success,NSData *data,char needDiv,NSError *error){finish(NO,success!=0,data,needDiv!=0,error);});
 BOOL completed=dispatch_semaphore_wait(done,dispatch_time(DISPATCH_TIME_NOW,15*NSEC_PER_SEC))==0;
 [lock lock];
 if(!completed && !finished){finished=YES;r[@"status"]=@"service_reply_timeout";}
 [lock unlock];
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(!getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 signal(SIGALRM,Deadline);alarm(30);
 if(argc==2 && !strcmp(argv[1],"--error-contract")) {
   BOOL ok=ServiceErrorContract();puts(ok?"service error contract passed":"service error contract failed");return ok?0:4;
 }
 if(argc!=3 || (strcmp(argv[2],"zero") && strcmp(argv[2],"nonzero")))return 2;
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-commerce-keybag-v1",@"status":@"interface_unavailable",
   @"account_login_attempted":@NO,@"authorization_request_attempted":@NO,@"keybag_import_attempted":@NO,
   @"enrollment_created":@NO,@"decryption_proven":@NO,@"running_as_root":B(geteuid()==0),@"transaction_type":@2} mutableCopy];
 r[@"state_before"]=State();
 @try {CommerceRequest(!strcmp(argv[2],"nonzero"),r);}
 @catch(NSException *error){r[@"status"]=@"native_exception";}
 r[@"state_after"]=State();
 NSData *out=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return out && [out writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
