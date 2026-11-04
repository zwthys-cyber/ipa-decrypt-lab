// Account-free policy/signature probe. Never submits an authorization request.
#define main NativeKeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main

static id Await(id promise,NSError *__autoreleasing *error) {
 SEL result=NSSelectorFromString(@"resultWithTimeout:error:");
 if(!ABI(promise,result,@"@",@[@"d",@"^@"]))return nil;
 return ((id(*)(id,SEL,double,NSError *__autoreleasing *))objc_msgSend)(promise,result,30.0,error);
}
static id BagValue(id bag,NSString *key,NSString *type,NSError *__autoreleasing *error) {
 SEL getter=NSSelectorFromString(type);
 if(!ABI(bag,getter,@"@",@[@"@"]))return nil;
 id item=((id(*)(id,SEL,id))objc_msgSend)(bag,getter,key);
 SEL value=NSSelectorFromString(@"valuePromise");
 if(!ABI(item,value,@"@",@[]))return nil;
 return Await(((id(*)(id,SEL))objc_msgSend)(item,value),error);
}
static void Probe(NSMutableDictionary *r) {
 Class authorizer=NSClassFromString(@"AMSAuthorizeMachineTask");
 SEL create=NSSelectorFromString(@"createBagForSubProfile");
 if(!ABI(authorizer,create,@"@",@[]))return;
 id bag=((id(*)(id,SEL))objc_msgSend)(authorizer,create);
 NSError *error=nil;
 id endpoint=BagValue(bag,@"authorizeMachine",@"URLForKey:",&error);
 ErrorFields(r,error);if(error || ![endpoint isKindOfClass:NSURL.class])return;
 NSURLComponents *url=[NSURLComponents componentsWithURL:endpoint resolvingAgainstBaseURL:NO];
 BOOL allowed=[url.scheme isEqual:@"https"] && [url.host isEqual:@"buy.itunes.apple.com"]
   && [url.path isEqual:@"/commerce/machine/authorize"] && !url.user && !url.password && !url.fragment
   && !url.query && (!url.port || url.port.integerValue==443);
 r[@"endpoint_supported"]=B(allowed);if(!allowed)return;
 id encoder=[NSClassFromString(@"AMSURLRequestEncoder") alloc];
 SEL init=NSSelectorFromString(@"initWithBag:");
 if(!ABI(encoder,init,@"@",@[@"@"]))return;
 encoder=((id(*)(id,SEL,id))objc_msgSend)(encoder,init,bag);
 SEL mescalType=NSSelectorFromString(@"mescalType");
 if(!ABI(encoder,mescalType,@"q",@[]))return;
 r[@"native_default_mescal_one"]=B(((long long(*)(id,SEL))objc_msgSend)(encoder,mescalType)==1);

 Class mescal=NSClassFromString(@"AMSMescal");
 id sap=BagValue(bag,@"sign-sap-request",@"dictionaryForKey:",&error);
 ErrorFields(r,error);if(error || ![sap isKindOfClass:NSDictionary.class]){r[@"status"]=@"policy_unavailable";return;}
 SEL match=NSSelectorFromString(@"_matchSignSapURL:bagDictionary:");
 if(!(ABI(mescal,match,@"B",@[@"@",@"@"])||ABI(mescal,match,@"c",@[@"@",@"@"])))return;
 r[@"sap_policy_matches"]=B(((BOOL(*)(id,SEL,id,id))objc_msgSend)(mescal,match,endpoint,sap));
 id actions=BagValue(bag,@"signed-actions",@"dictionaryForKey:",&error);
 ErrorFields(r,error);if(error || ![actions isKindOfClass:NSDictionary.class]){r[@"status"]=@"policy_unavailable";return;}
 match=NSSelectorFromString(@"_matchSignedActions:withURL:");
 if(!ABI(mescal,match,@"@",@[@"@",@"@"]))return;
 id actionPolicy=((id(*)(id,SEL,id,id))objc_msgSend)(mescal,match,actions,endpoint);
 r[@"action_policy_matches"]=B(actionPolicy!=nil);
 r[@"policy_checked"]=@YES;

 NSMutableURLRequest *request=[NSMutableURLRequest requestWithURL:endpoint];
 request.HTTPMethod=@"POST";
 NSDictionary *fixture=@{@"ownerDsid":@1234567,@"xToken":@"ipa-lab-synthetic-token",@"guid":@"001122334455",
   @"machineName":@"Synthetic fixture",@"kbsync":@"U1lOVEhFVElD",@"needDiv":@1};
 request.HTTPBody=[NSPropertyListSerialization dataWithPropertyList:fixture format:NSPropertyListXMLFormat_v1_0 options:0 error:NULL];
 [request setValue:@"application/x-apple-plist" forHTTPHeaderField:@"Content-Type"];
 [request setValue:[NSString stringWithFormat:@"%lu",(unsigned long)request.HTTPBody.length] forHTTPHeaderField:@"Content-Length"];
 NSData *body=[request.HTTPBody copy];NSDictionary *headers=[request.allHTTPHeaderFields copy];
 Class decoration=NSClassFromString(@"AMSURLRequestDecoration");
 SEL sign=NSSelectorFromString(@"addMescalHeaderToRequest:type:bag:logKey:");
 if(!ABI(decoration,sign,@"@",@[@"@",@"q",@"@",@"@"]))return;
 r[@"signing_attempted"]=@YES;
 id promise=((id(*)(id,SEL,id,long long,id,id))objc_msgSend)(decoration,sign,request,1,bag,nil);
 id result=Await(promise,&error);ErrorFields(r,error);
 r[@"signing_result_present"]=B(result!=nil);
 NSString *signature=[request valueForHTTPHeaderField:@"X-Apple-ActionSignature"];
 BOOL present=signature.length>0;
 NSData *decoded=present && signature.length<=16384?[[NSData alloc] initWithBase64EncodedString:signature options:0]:nil;
 r[@"signature_present"]=B(present);r[@"signature_valid"]=B(decoded.length>0);
 r[@"body_unchanged"]=B([body isEqual:request.HTTPBody]);
 r[@"destination_unchanged"]=B([endpoint isEqual:request.URL] && [request.HTTPMethod isEqual:@"POST"]);
 NSMutableDictionary *after=[request.allHTTPHeaderFields mutableCopy];
 for(NSString *key in [after.allKeys copy])if([key caseInsensitiveCompare:@"X-Apple-ActionSignature"]==NSOrderedSame)[after removeObjectForKey:key];
 r[@"other_headers_unchanged"]=B([headers isEqual:after]);
 r[@"status"]=error?@"signing_failed":(decoded.length?@"signature_ready":@"signature_not_requested");
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(argc!=2 || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 NSMutableDictionary *r=[@{@"status":@"interface_unavailable"} mutableCopy];
 @try {
   dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL);
   dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL);
   Probe(r);
 } @catch(NSException *e){r[@"status"]=@"native_exception";}
 NSData *data=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return data && [data writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
