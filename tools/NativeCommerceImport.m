// Fixed invalid bags only, in a disposable GitHub runner. No credentials or network authorization.
#define LAB_COMMERCE_LIBRARY 1
#include "NativeCommerceKeybag.m"

static void ImportControl(BOOL invalid,NSMutableDictionary *r) {
 BOOL loaded=dlopen("/System/Library/PrivateFrameworks/CommerceKit.framework/CommerceKit",RTLD_NOW|RTLD_GLOBAL)!=NULL;
 r[@"framework_loaded"]=B(loaded);if(!loaded){r[@"status"]=@"framework_unavailable";return;}
 id account=SyntheticAccount(YES,r);
 if(!account){r[@"status"]=@"synthetic_account_unavailable";return;}
 Class cls=NSClassFromString(@"ServiceProxy");
 SEL get=NSSelectorFromString(@"commerceServiceWithErrorHandler:");
 if(!ABI(cls,get,@"@",@[@"@?"])){r[@"status"]=@"interface_unavailable";return;}
 NSLock *errorLock=[NSLock new];NSMutableDictionary *transport=[NSMutableDictionary dictionary];
 id service=((id(*)(id,SEL,id))objc_msgSend)(cls,get,^(NSError *error){
   [errorLock lock];
   transport[@"transport_error_received"]=@YES;
   if([error isKindOfClass:NSError.class]){ErrorFields(transport,error);ServiceErrorFields(transport,error);}
   [errorLock unlock];
 });
 SEL generate=NSSelectorFromString(@"kbSyncForTransactionType:account:reply:");
 BOOL syncABI=ABI(service,generate,@"v",@[@"C",@"@",@"@?"]) || ABI(service,generate,@"v",@[@"c",@"@",@"@?"]);
 SEL import=NSSelectorFromString(@"importKeyBag:diversityBag:");
 BOOL importABI=ABI(service,import,@"v",@[@"@",@"@"]);
 r[@"sync_abi_verified"]=B(syncABI);r[@"import_abi_verified"]=B(importABI);
 if(!syncABI || !importABI){r[@"status"]=@"interface_unavailable";return;}
 r[@"baseline"]=CommerceSyncObservation(service,account);
 if(!CommerceSyncReady(r[@"baseline"])){r[@"status"]=@"baseline_unavailable";return;}
 r[@"state_before"]=State();
 if(invalid) {
   // The only accepted import fixture is two fixed zero-filled byte arrays.
   NSData *bag=[NSData dataWithBytes:(const unsigned char[32]){0} length:32];
   NSData *diversity=[NSData dataWithBytes:(const unsigned char[16]){0} length:16];
   r[@"keybag_import_attempted"]=@YES;Checkpoint(r,@"import_submitting");
   ((void(*)(id,SEL,id,id))objc_msgSend)(service,import,bag,diversity);
   r[@"import_call_returned"]=@YES;Checkpoint(r,@"import_submitted");
 }
 r[@"followup"]=CommerceSyncObservation(service,account);
 // A follow-up reply proves availability only, not processing order or import completion.
 [NSThread sleepForTimeInterval:1.0];
 r[@"state_after"]=State();
 [errorLock lock];[r addEntriesFromDictionary:transport];[errorLock unlock];
 r[@"status"]=[r[@"transport_error_received"] boolValue]?@"transport_failed":
   !CommerceSyncReady(r[@"followup"])?@"followup_unavailable":
   invalid?@"submission_unverified":@"baseline_complete";
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(!getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 if(argc!=3 || (strcmp(argv[2],"baseline") && strcmp(argv[2],"invalid-both")))return 2;
 signal(SIGALRM,Deadline);alarm(25);
 BOOL invalid=!strcmp(argv[2],"invalid-both");
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-commerce-import-v1",@"status":@"probe_failed",
   @"fixture":invalid?@"invalid-both":@"baseline",@"running_as_root":B(geteuid()==0),
   @"account_login_attempted":@NO,@"authorization_request_attempted":@NO,
   @"keybag_import_attempted":@NO,@"import_call_returned":@NO,@"import_verified":@NO,
   @"enrollment_created":@NO,@"decryption_proven":@NO,@"transport_error_received":@NO} mutableCopy];
 CheckpointPath=@(argv[1]);Checkpoint(r,@"started");
 @try {ImportControl(invalid,r);}
 @catch(NSException *exception){r[@"status"]=@"native_exception";}
 NSData *out=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return out && [out writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
