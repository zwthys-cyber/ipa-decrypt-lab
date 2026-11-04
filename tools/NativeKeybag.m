// Account-free local FairPlay prerequisites; never authorizes or imports a keybag.
#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>
#import <dlfcn.h>
static NSNumber *B(BOOL v) { return v ? @YES : @NO; }
static NSDictionary *Specs(void) {
 return @{
 @"AMSKeybag": @[@"+sharedInstance",@"-init",@"-fairplayContextWithError:",@"-keybagSyncDataWithAccountID:transactionType:error:",@"-keybagSyncData:transactionType:outError:",@"-importKeybagWithData:error:",@"-importKeybagData:outError:",@"-resetContext"],
 @"AMSFairPlayContext": @[@"-init",@"-fairplayContextIDWithError:",@"-destroyContext"],
 @"AMSAuthorizeMachineTask": @[@"+createBagForSubProfile",@"+bagSubProfile",@"-initWithAccount:authorizeReason:bag:",@"-_buildRequestParametersWithError:",@"-performAuthorization",@"-performDeauthorization"],
 @"ASDFairPlayService": @[@"+defaultService",@"-generateKeybagRequestForDSID:error:",@"-importKeybag:error:"],
 @"ACAccount": @[@"+ams_createEphemeralAccount",@"-ams_setDSID:",@"-ams_DSID",@"-ams_setPassword:",@"-ams_password",@"-ams_isEphemeralAccount",@"-ams_setStorefront:",@"-ams_setRawPassword:"],
 @"AMSBag": @[@"+bagForProfile:profileVersion:",@"-URLForKey:"],
 @"AMSPromise": @[@"-resultWithError:",@"-addFinishBlock:"]};
}
static NSDictionary *State(void) {
 NSMutableDictionary *r=[NSMutableDictionary dictionary];
 NSDictionary *paths=@{@"fpsd_sidb":@"/private/var/db/fpsd/SC Info/SC Info.sidb",
 @"fpsd_sids":@"/private/var/db/fpsd/SC Info/SC Info.sids",
 @"shared_sidb":@"/Users/Shared/SC Info/SC Info.sidb",@"shared_sids":@"/Users/Shared/SC Info/SC Info.sids"};
 for(NSString *key in paths) {
   NSDictionary *a=[[NSFileManager defaultManager] attributesOfItemAtPath:paths[key] error:NULL];
   r[key]=B([a[NSFileType] isEqualToString:NSFileTypeRegular] && [a[NSFileSize] unsignedLongLongValue]>0);
 }
 return r;
}
static void ErrorFields(NSMutableDictionary *r,NSError *e) {
 r[@"error_present"]=B(e!=nil); if(!e)return;
 NSSet *ds=[NSSet setWithArray:@[@"AMSErrorDomain",@"ASDErrorDomain",@"SSErrorDomain",@"NSCocoaErrorDomain",@"NSPOSIXErrorDomain",@"NSOSStatusErrorDomain",@"NSURLErrorDomain"]];
 r[@"error_domain"]=[ds containsObject:e.domain]?e.domain:@"other";
 if(e.code>=-999999 && e.code<=999999)r[@"error_code"]=@(e.code);
 NSString *d=e.localizedDescription;
 if(d.length && d.length<4096) {
   NSRegularExpression *re=[NSRegularExpression regularExpressionWithPattern:@"status: (-?[0-9]{1,6})(?![0-9])" options:0 error:NULL];
   NSTextCheckingResult *m=[re firstMatchInString:d options:0 range:NSMakeRange(0,d.length)];
   if(m)r[@"fairplay_status"]=@([[d substringWithRange:[m rangeAtIndex:1]] integerValue]);
 }
}
static BOOL ABI(id target,SEL sel,NSString *ret,NSArray<NSString *> *args) {
 NSMethodSignature *sig=[target methodSignatureForSelector:sel];
 if(!sig || sig.numberOfArguments!=args.count+2 || ![@(sig.methodReturnType) isEqualToString:ret])return NO;
 for(NSUInteger i=0;i<args.count;i++)if(![@([sig getArgumentTypeAtIndex:i+2]) isEqualToString:args[i]])return NO;
 return YES;
}
static NSDictionary *Interfaces(void) {
 NSMutableDictionary *r=[NSMutableDictionary dictionary]; NSDictionary *specs=Specs();
 for(NSString *name in specs) {
   Class cls=NSClassFromString(name); NSMutableDictionary *methods=[NSMutableDictionary dictionary];
   for(NSString *entry in specs[name]) {
     SEL sel=NSSelectorFromString([entry substringFromIndex:1]);
     Method m=[entry hasPrefix:@"+"]?class_getClassMethod(cls,sel):class_getInstanceMethod(cls,sel);
     const char *enc=m?method_getTypeEncoding(m):NULL;
     methods[entry]=enc?@(enc):(id)[NSNull null];
   }
   r[name]=@{@"present":B(cls!=Nil),@"methods":methods};
 }
 return r;
}

static void Parameters(NSMutableDictionary *r) {
 Class cls=NSClassFromString(@"ACAccount");
 SEL create=NSSelectorFromString(@"ams_createEphemeralAccount");
 if(!ABI(cls,create,@"@",@[]))return;
 id account=((id(*)(id,SEL))objc_msgSend)(cls,create);
 SEL ep=NSSelectorFromString(@"ams_isEphemeralAccount");
 BOOL epABI=ABI(account,ep,@"B",@[]) || ABI(account,ep,@"c",@[]);
 BOOL ephemeral=epABI && ((BOOL(*)(id,SEL))objc_msgSend)(account,ep);
 r[@"ephemeral_account"]=B(ephemeral);
 SEL dsid=NSSelectorFromString(@"ams_setDSID:");
 if(!ephemeral || !ABI(account,dsid,@"v",@[@"@"]))return;
 ((void(*)(id,SEL,id))objc_msgSend)(account,dsid,@0);
 id task=[NSClassFromString(@"AMSAuthorizeMachineTask") alloc];
 SEL init=NSSelectorFromString(@"initWithAccount:authorizeReason:bag:");
 if(!ABI(task,init,@"@",@[@"@",@"Q",@"@"]))return;
 task=((id(*)(id,SEL,id,unsigned long long,id))objc_msgSend)(task,init,account,0,nil);
 SEL build=NSSelectorFromString(@"_buildRequestParametersWithError:");
 BOOL ok=ABI(task,build,@"@",@[@"^@"]);r[@"abi_verified"]=B(ok);
 if(!ok)return;
 NSError *error=nil;
 id params=((id(*)(id,SEL,NSError *__autoreleasing *))objc_msgSend)(task,build,&error);
 ErrorFields(r,error);
 BOOL valid=[params isKindOfClass:NSDictionary.class];
 id sync=valid?params[@"kbsync"]:nil;
 NSData *data=[sync isKindOfClass:NSString.class]?[[NSData alloc] initWithBase64EncodedString:sync options:0]:nil;
 BOOL present=data.length>0 && data.length<=1048576;
 r[@"sync_data_present"]=B(present);
 if(present)r[@"sync_data_length"]=@(data.length);
 id guid=valid?params[@"guid"]:nil;
 r[@"guid_is_six_bytes"]=B([guid isKindOfClass:NSString.class] && [guid rangeOfString:@"^[A-Fa-f0-9]{12}$" options:NSRegularExpressionSearch].location!=NSNotFound);
 id owner=valid?params[@"ownerDsid"]:nil;
 r[@"owner_is_synthetic"]=B([owner isKindOfClass:NSNumber.class] && [owner isEqualToNumber:@0]);
 r[@"machine_name_present"]=B([params[@"machineName"] isKindOfClass:NSString.class] && [params[@"machineName"] length]>0);
 r[@"parameter_names_valid"]=B(valid && [[NSSet setWithArray:[params allKeys]] isEqualToSet:[NSSet setWithArray:@[@"kbsync",@"guid",@"machineName",@"ownerDsid"]]]);
 r[@"status"]=valid && present && !error?@"synthetic_parameters_ready":@"synthetic_parameters_failed";
}
static void PublicBag(NSMutableDictionary *r) {
 Class cls=NSClassFromString(@"AMSAuthorizeMachineTask");
 SEL create=NSSelectorFromString(@"createBagForSubProfile");
 if(!ABI(cls,create,@"@",@[]))return;
 id bag=((id(*)(id,SEL))objc_msgSend)(cls,create);
 SEL get=NSSelectorFromString(@"URLForKey:");
 if(!ABI(bag,get,@"@",@[@"@"]))return;
 id value=((id(*)(id,SEL,id))objc_msgSend)(bag,get,@"authorizeMachine");
 SEL promiseSel=NSSelectorFromString(@"valuePromise");
 if(!ABI(value,promiseSel,@"@",@[]))return;
 id promise=((id(*)(id,SEL))objc_msgSend)(value,promiseSel);
 SEL resultSel=NSSelectorFromString(@"resultWithTimeout:error:");
 BOOL ok=ABI(promise,resultSel,@"@",@[@"d",@"^@"]);r[@"abi_verified"]=B(ok);
 if(!ok)return;
 NSError *error=nil;
 id result=((id(*)(id,SEL,double,NSError *__autoreleasing *))objc_msgSend)(promise,resultSel,12.0,&error);
 ErrorFields(r,error);
 BOOL url=[result isKindOfClass:NSURL.class];
 r[@"bag_url_present"]=B(url);
 if(url) {
   NSURLComponents *c=[NSURLComponents componentsWithURL:result resolvingAgainstBaseURL:NO];
   BOOL host=[c.host rangeOfString:@"^(buy|p[0-9]{1,3}-buy|finance-app)\\.itunes\\.apple\\.com$" options:NSRegularExpressionSearch].location!=NSNotFound;
   BOOL path=[c.path rangeOfString:@"^/WebObjects/MZFinance\\.woa/wa/authorizeMachine/?$" options:NSRegularExpressionSearch].location!=NSNotFound;
   r[@"endpoint_supported"]=B([c.scheme isEqualToString:@"https"] && host && path && !c.user && !c.password && (!c.port || c.port.integerValue==443));
   if(host)r[@"endpoint_host"]=c.host;
   if(path)r[@"endpoint_path"]=c.path;
   r[@"endpoint_query_present"]=B(c.query.length>0);
 }
 r[@"status"]=url && !error?@"public_bag_ready":@"public_bag_failed";
}

int main(int argc,const char **argv) { @autoreleasepool {
 if(argc!=3 || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 NSString *mode=@(argv[1]); if(![@[@"interfaces",@"context",@"kbsync",@"parameters",@"public_bag"] containsObject:mode])return 2;
 NSMutableDictionary *r=[@{@"mode":mode,@"status":@"interface_unavailable",@"account_login_attempted":@NO,@"enrollment_created":@NO,@"decryption_proven":@NO} mutableCopy];
 @try {
   r[@"state_before"]=State();
   void *ams=dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL);
   dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL);
   dlopen("/System/Library/PrivateFrameworks/AppStoreDaemon.framework/AppStoreDaemon",RTLD_NOW|RTLD_GLOBAL);
   r[@"ams_loaded"]=B(ams!=NULL);
   if([mode isEqualToString:@"interfaces"]) {
     r[@"interfaces"]=Interfaces(); NSMutableDictionary *keys=[NSMutableDictionary dictionary];
     for(NSString *symbol in @[@"AMSBagKeyAuthorizeMachineURL",@"AMSBagKeyDeauthorizeMachineURL"]) {
       NSString *__unsafe_unretained *p=(NSString *__unsafe_unretained *)dlsym(RTLD_DEFAULT,symbol.UTF8String);
       NSString *v=p?*p:nil;
       if([v isKindOfClass:NSString.class] && [v rangeOfString:@"^[a-zA-Z0-9-]{1,80}$" options:NSRegularExpressionSearch].location!=NSNotFound)keys[symbol]=v;
     }
     r[@"bag_keys"]=keys; r[@"status"]=@"interfaces_checked";
   } else if([mode isEqualToString:@"parameters"]) {
     Parameters(r);
   } else if([mode isEqualToString:@"public_bag"]) {
     PublicBag(r);
   } else if([mode isEqualToString:@"context"]) {
     id context=[[NSClassFromString(@"AMSFairPlayContext") alloc] init]; SEL s=NSSelectorFromString(@"fairplayContextIDWithError:");
     BOOL ok=ABI(context,s,@"I",@[@"^@"]); r[@"abi_verified"]=B(ok);
     if(ok) {
       NSError *e=nil; unsigned int ident=((unsigned int(*)(id,SEL,NSError *__autoreleasing *))objc_msgSend)(context,s,&e);
       ErrorFields(r,e); r[@"context_ready"]=B(ident!=0 && !e);
       r[@"status"]=ident!=0 && !e?@"context_ready":@"context_failed";
     }
     if(ABI(context,NSSelectorFromString(@"destroyContext"),@"v",@[]))((void(*)(id,SEL))objc_msgSend)(context,NSSelectorFromString(@"destroyContext"));
   } else {
     id bag=[[NSClassFromString(@"AMSKeybag") alloc] init];
     SEL s=NSSelectorFromString(@"keybagSyncDataWithAccountID:transactionType:error:");
     if(!ABI(bag,s,@"@",@[@"@",@"I",@"^@"]))s=NSSelectorFromString(@"keybagSyncData:transactionType:outError:");
     BOOL ok=ABI(bag,s,@"@",@[@"@",@"I",@"^@"]);r[@"abi_verified"]=B(ok);
     if(ok) {
       NSError *e=nil; id data=((id(*)(id,SEL,id,unsigned int,NSError *__autoreleasing *))objc_msgSend)(bag,s,@0,1,&e);
       ErrorFields(r,e);
       BOOL present=[data isKindOfClass:NSData.class] && [data length]>0 && [data length]<=1048576;
       r[@"sync_data_present"]=B(present);if(present)r[@"sync_data_length"]=@([data length]);
       r[@"synthetic_account_id"]=@YES;r[@"transaction_type"]=@1;
       r[@"status"]=present && !e?@"synthetic_sync_ready":@"synthetic_sync_failed";
     }
     if(ABI(bag,NSSelectorFromString(@"resetContext"),@"v",@[]))((void(*)(id,SEL))objc_msgSend)(bag,NSSelectorFromString(@"resetContext"));
   }
   r[@"state_after"]=State();
 } @catch(NSException *e) {r[@"status"]=@"native_exception";}
 NSData *out=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return out && [out writeToFile:@(argv[2]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
