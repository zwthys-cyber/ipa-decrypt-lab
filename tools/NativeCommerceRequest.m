// Construct a request from fixed values; never execute the returned URL request.
#define LAB_COMMERCE_LIBRARY 1
#include "NativeCommerceKeybag.m"
#include "CommerceSessionBinding.h"
@protocol LabStoreRequestInitializing <NSObject>
- (instancetype)initWithStoreClient:(id)client URL:(id)URL;
@end
static void BuildCommerceRequest(NSDictionary *input,NSMutableDictionary *r) {
 BOOL loaded=dlopen("/System/Library/PrivateFrameworks/CommerceKit.framework/CommerceKit",RTLD_NOW|RTLD_GLOBAL)!=NULL;
 r[@"framework_loaded"]=B(loaded);if(!loaded){r[@"status"]=@"framework_unavailable";return;}
 id account=SyntheticAccount(YES,r);
 if(!account){r[@"status"]=@"synthetic_account_unavailable";return;}
 Class clientClass=NSClassFromString(@"CKStoreClient"),contextClass=NSClassFromString(@"CKMachineAuthorizationContext");
 SEL clientFactory=NSSelectorFromString(@"storeClientForIdentifier:");
 SEL contextFactory=NSSelectorFromString(@"machineAuthorizationContextWithStoreClient:");
 SEL setToken=NSSelectorFromString(@"_setToken:"),getToken=NSSelectorFromString(@"_token");
 if(!ABI(clientClass,clientFactory,@"@",@[@"@"]) || !ABI(contextClass,contextFactory,@"@",@[@"@"])
     || !ABI(account,setToken,@"v",@[@"@"]) || !ABI(account,getToken,@"@",@[]))return;
 id client=((id(*)(id,SEL,id))objc_msgSend)(clientClass,clientFactory,@"com.apple.configurator.ui");
 id context=((id(*)(id,SEL,id))objc_msgSend)(contextClass,contextFactory,client);
 NSString *token=@"ipa-lab-fixed-not-a-real-token";
 ((void(*)(id,SEL,id))objc_msgSend)(account,setToken,token);
 r[@"synthetic_token_verified"]=B([((id(*)(id,SEL))objc_msgSend)(account,getToken) isEqual:token]);
 SEL bodySelector=NSSelectorFromString(@"_requestBodyForAccount:bagURLKey:");
 r[@"body_abi_verified"]=B(ABI(context,bodySelector,@"@",@[@"@",@"@"]));
 if(![r[@"body_abi_verified"] boolValue] || ![r[@"synthetic_token_verified"] boolValue])return;
 Checkpoint(r,@"building_body");
 id supplied=((id(*)(id,SEL,id,id))objc_msgSend)(context,bodySelector,account,@"authorizeMachine");
 NSDictionary *body=[supplied isKindOfClass:NSDictionary.class]?supplied:nil;
 r[@"body_created"]=B(body!=nil);
 id sync=body[@"kbsync"],needDiv=body[@"needDiv"];
 NSData *syncData=[sync isKindOfClass:NSString.class] && [sync length]<=2796204?
   [[NSData alloc] initWithBase64EncodedString:sync options:0]:nil;
 r[@"body_sync_present"]=B(syncData.length>0 && syncData.length<=2097152);
 r[@"body_token_matches"]=B([body[@"xToken"] isEqual:token]);
 BOOL divValid=[needDiv isKindOfClass:NSString.class] && ([(NSString *)needDiv isEqual:@"0"] || [(NSString *)needDiv isEqual:@"1"]);
 r[@"body_needdiv_valid"]=B(divValid);r[@"need_diversitybag"]=B([needDiv isEqual:@"1"]);
 r[@"body_machine_name_present"]=B([body[@"machineName"] isKindOfClass:NSString.class] && [body[@"machineName"] length]>0);
 r[@"body_parameter_names_valid"]=B(body && [[NSSet setWithArray:body.allKeys]
   isEqualToSet:[NSSet setWithArray:@[@"machineName",@"kbsync",@"needDiv",@"xToken"]]]);
 if(![r[@"body_sync_present"] boolValue] || ![r[@"body_token_matches"] boolValue] || !divValid
     || ![r[@"body_parameter_names_valid"] boolValue]){r[@"status"]=@"body_unverified";return;}
 Class requestClass=NSClassFromString(@"CKStoreRequest");
 SEL initializer=@selector(initWithStoreClient:URL:);
 if(!InstanceABI(requestClass,initializer,@"@",@[@"@",@"@"]))return;
 id request=[(id<LabStoreRequestInitializing>)[requestClass alloc] initWithStoreClient:client
   URL:[NSURL URLWithString:@"https://buy.itunes.apple.com/commerce/machine/authorize"]];
 SEL setBody=NSSelectorFromString(@"setBodyPlist:"),build=NSSelectorFromString(@"_URLRequestWithError:");
 r[@"request_abi_verified"]=B(ABI(request,setBody,@"v",@[@"@"]) && ABI(request,build,@"@",@[@"^@"]));
 if(![r[@"request_abi_verified"] boolValue])return;
 ((void(*)(id,SEL,id))objc_msgSend)(request,setBody,body);
 Checkpoint(r,@"building_request");
 NSError *error=nil;
 id candidate=((id(*)(id,SEL,NSError *__autoreleasing *))objc_msgSend)(request,build,&error);
 ErrorFields(r,error);ServiceErrorFields(r,error);
 NSURLRequest *urlRequest=[candidate isKindOfClass:NSURLRequest.class]?candidate:nil;
 r[@"request_created"]=B(urlRequest!=nil);if(!urlRequest || error){r[@"status"]=@"request_unavailable";return;}
 NSURL *url=urlRequest.URL;
 r[@"request_https"]=B([url.scheme isEqual:@"https"]);
 r[@"request_host_allowed"]=B([url.host isEqual:@"buy.itunes.apple.com"]);
 r[@"request_path_allowed"]=B([url.path isEqual:@"/commerce/machine/authorize"]);
 r[@"request_is_post"]=B([urlRequest.HTTPMethod isEqual:@"POST"]);
 NSString *agent=[urlRequest valueForHTTPHeaderField:@"User-Agent"];
 r[@"request_user_agent_configurator"]=B([agent hasPrefix:@"Configurator/"]);
 r[@"request_ds_header_matches"]=B([[urlRequest valueForHTTPHeaderField:@"X-Dsid"] isEqual:@"1234567"]);
 r[@"request_has_anisette"]=B([urlRequest valueForHTTPHeaderField:@"X-Apple-I-MD"].length>0
   && [urlRequest valueForHTTPHeaderField:@"X-Apple-I-MD-M"].length>0);
 NSData *wire=urlRequest.HTTPBody;
 id decoded=wire.length>0 && wire.length<=4194304?
   [NSPropertyListSerialization propertyListWithData:wire options:NSPropertyListImmutable format:NULL error:NULL]:nil;
 NSDictionary *wireBody=[decoded isKindOfClass:NSDictionary.class]?decoded:nil;
 r[@"request_body_is_plist"]=B(wireBody!=nil);
 r[@"body_sync_preserved"]=B([wireBody[@"kbsync"] isEqual:sync]);
 r[@"body_token_preserved"]=B([wireBody[@"xToken"] isEqual:token]);
 r[@"body_needdiv_preserved"]=B([wireBody[@"needDiv"] isEqual:needDiv]);
 r[@"body_owner_present"]=B(wireBody[@"ownerDsid"]!=nil);
 r[@"body_owner_matches_synthetic"]=B([wireBody[@"ownerDsid"] isEqual:@1234567] || [wireBody[@"ownerDsid"] isEqual:@"1234567"]);
 id guid=wireBody[@"guid"];
 r[@"body_guid_is_six_bytes"]=B([guid isKindOfClass:NSString.class]
   && [guid rangeOfString:@"^[A-Fa-f0-9]{12}$" options:NSRegularExpressionSearch].location!=NSNotFound);
 BOOL good=YES;for(NSString *key in @[@"request_https",@"request_host_allowed",@"request_path_allowed",
     @"request_is_post",@"request_body_is_plist",@"body_sync_preserved",@"body_token_preserved",@"body_needdiv_preserved"])
   good=good && [r[key] boolValue];
 if(!good){r[@"status"]=@"request_shape_unverified";return;}
 r[@"native_guid_matches_login"]=B([guid isKindOfClass:NSString.class] && [guid isEqual:input[@"guid"]]);
 NSMutableURLRequest *bound=LabBindCommerceSession(urlRequest,@1234567,token,input[@"guid"],input[@"user_agent"]);
 r[@"session_bound"]=B(bound!=nil);
 if(!bound){r[@"status"]=@"session_binding_failed";return;}
 NSDictionary *boundBody=[NSPropertyListSerialization propertyListWithData:bound.HTTPBody options:NSPropertyListImmutable format:NULL error:NULL];
 r[@"session_user_agent_bound"]=B([[bound valueForHTTPHeaderField:@"User-Agent"] isEqual:input[@"user_agent"]]);
 r[@"session_owner_bound"]=B([boundBody[@"ownerDsid"] isEqual:@1234567]);
 r[@"session_dsid_headers_bound"]=B([[bound valueForHTTPHeaderField:@"X-Dsid"] isEqual:@"1234567"]
   && [[bound valueForHTTPHeaderField:@"iCloud-DSID"] isEqual:@"1234567"]);
 r[@"session_token_header_bound"]=B([[bound valueForHTTPHeaderField:@"X-Token"] isEqual:token]);
 r[@"native_guid_preserved"]=B([boundBody[@"guid"] isEqual:guid]);
 r[@"sync_preserved_after_binding"]=B([boundBody[@"kbsync"] isEqual:sync]);
 r[@"token_preserved_after_binding"]=B([boundBody[@"xToken"] isEqual:token]);
 r[@"needdiv_preserved_after_binding"]=B([boundBody[@"needDiv"] isEqual:needDiv]);
 r[@"content_length_matches"]=B([[bound valueForHTTPHeaderField:@"Content-Length"] longLongValue]==(long long)bound.HTTPBody.length);
 r[@"bound_route_valid"]=B(LabCommerceRoute(bound,input[@"guid"]));
 BOOL headersPreserved=YES;
 for(NSString *key in @[@"X-Apple-I-MD",@"X-Apple-I-MD-M"]) {
   NSString *before=[urlRequest valueForHTTPHeaderField:key],*after=[bound valueForHTTPHeaderField:key];
   headersPreserved=headersPreserved && ((!before && !after) || [before isEqual:after]);
 }
 r[@"anisette_preserved_after_binding"]=B(headersPreserved);
 r[@"status"]=@"synthetic_session_bound";
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(!getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true") || argc!=2)return 2;
 signal(SIGALRM,Deadline);alarm(25);
 if(!strcmp(argv[1],"--binding-contract")) {
   BOOL ok=LabCommerceBindingContract();puts(ok?"commerce binding contract passed":"commerce binding contract failed");return ok?0:4;
 }
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-commerce-request-v1",@"status":@"interface_unavailable",
   @"account_login_attempted":@NO,@"authorization_request_attempted":@NO,@"keybag_import_attempted":@NO,
   @"enrollment_created":@NO,@"decryption_proven":@NO,@"running_as_root":B(geteuid()==0)} mutableCopy];
 CheckpointPath=@(argv[1]);Checkpoint(r,@"started");r[@"state_before"]=State();
 unsigned char inputBytes[4097];size_t count=fread(inputBytes,1,sizeof(inputBytes),stdin);
 id input=count>0 && count<sizeof(inputBytes)?[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:inputBytes length:count] options:0 error:NULL]:nil;
 BOOL valid=[input isKindOfClass:NSDictionary.class] && [input[@"guid"] isKindOfClass:NSString.class]
   && [input[@"guid"] rangeOfString:@"^[A-F0-9]{12}$" options:NSRegularExpressionSearch].location!=NSNotFound
   && [input[@"user_agent"] isKindOfClass:NSString.class];
 @try {if(valid)BuildCommerceRequest(input,r);else r[@"status"]=@"private_identity_unavailable";}
 @catch(NSException *exception){r[@"status"]=@"native_exception";}
 r[@"state_after"]=State();
 NSData *out=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return out && [out writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
