// One machine-authorization request using an existing private Store session.
// Reuse audited ABI, state-report, and destination/identity checks.
#define main KeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main


static NSDictionary *AnisetteResponseFields(NSHTTPURLResponse *response) {
 NSMutableDictionary *headers=[NSMutableDictionary dictionary],*result=[NSMutableDictionary dictionary];
 for(id key in response.allHeaderFields)if([key isKindOfClass:NSString.class])headers[[key lowercaseString]]=response.allHeaderFields[key];
 for(NSString *scope in @[@"md",@"amd"]) {
   NSString *prefix=[NSString stringWithFormat:@"x-apple-%@",scope];
   id action=headers[[prefix stringByAppendingString:@"-action"]];
   id encoded=headers[[prefix stringByAppendingString:@"-data"]];
   NSString *kind=@"none";
   if(action && ![action isEqual:@""])kind=[@[@"SP",@"SM",@"RP"] containsObject:action]?action:@"other";
   BOOL present=[encoded isKindOfClass:NSString.class] && [encoded length]>0;
   NSData *decoded=present && [encoded length]<=1048576?[[NSData alloc] initWithBase64EncodedString:encoded options:0]:nil;
   result[[scope stringByAppendingString:@"_action"]]=kind;
   result[[scope stringByAppendingString:@"_data_present"]]=B(present);
   result[[scope stringByAppendingString:@"_data_valid"]]=B(decoded.length>0);
 }
 return result;
}
static BOOL ResponseContract(void) {
 NSURL *url=[NSURL URLWithString:@"https://buy.itunes.apple.com/commerce/machine/authorize"];
 NSHTTPURLResponse *(^response)(NSDictionary *)=^NSHTTPURLResponse *(NSDictionary *headers) {
   return [[NSHTTPURLResponse alloc] initWithURL:url statusCode:200 HTTPVersion:@"HTTP/1.1" headerFields:headers];
 };
 NSDictionary *empty=AnisetteResponseFields(response(@{}));
 NSDictionary *challenge=AnisetteResponseFields(response(@{@"x-APPLE-md-ACTION":@"SP",@"X-Apple-MD-Data":@"U1lOVEhFVElD",
   @"X-Apple-AMD-Action":@"SM",@"x-apple-amd-data":@"U1lOVEhFVElD",@"Set-Cookie":@"PRIVATE_SYNTHETIC"}));
 NSDictionary *bad=AnisetteResponseFields(response(@{@"X-Apple-MD-Action":@"PRIVATE_SYNTHETIC",@"X-Apple-MD-Data":@"not base64!"}));
 NSString *serialized=[[NSString alloc] initWithData:[NSJSONSerialization dataWithJSONObject:@[empty,challenge,bad] options:0 error:NULL] encoding:NSUTF8StringEncoding];
 return [empty[@"md_action"] isEqual:@"none"] && [empty[@"amd_action"] isEqual:@"none"]
   && ![empty[@"md_data_present"] boolValue] && ![empty[@"amd_data_valid"] boolValue]
   && [challenge[@"md_action"] isEqual:@"SP"] && [challenge[@"amd_action"] isEqual:@"SM"]
   && [challenge[@"md_data_valid"] boolValue] && [challenge[@"amd_data_valid"] boolValue]
   && [bad[@"md_action"] isEqual:@"other"] && [bad[@"md_data_present"] boolValue] && ![bad[@"md_data_valid"] boolValue]
   && ![serialized containsString:@"PRIVATE_SYNTHETIC"] && ![serialized containsString:@"U1lOVEhFVElD"];
}

@interface LabEnrollmentResponse : NSObject <NSURLSessionDataDelegate>
@property(nonatomic,strong) NSMutableData *data;
@property(nonatomic,strong) NSHTTPURLResponse *response;
@property(nonatomic,strong) NSError *error;
@property(nonatomic) BOOL redirected;
@property(nonatomic) BOOL redirectSeen;
@property(nonatomic,strong) NSDictionary *redirectSummary;
@property(nonatomic,strong) NSDictionary *storeContext;
@property(nonatomic) NSUInteger cookieCount;
@property(nonatomic) NSUInteger redirectCount;
@property(nonatomic,strong) NSURLRequest *originalRequest;
@property(nonatomic,strong) NSNumber *dsid;
@property(nonatomic,copy) NSString *token;
@property(nonatomic,copy) NSString *guid;
@property(nonatomic) BOOL oversized;
@property(nonatomic,strong) dispatch_semaphore_t done;
@end
@implementation LabEnrollmentResponse
- (instancetype)init {
 if((self=[super init])){_data=[NSMutableData data];_done=dispatch_semaphore_create(0);}return self;
}
- (void)URLSession:(NSURLSession *)session dataTask:(NSURLSessionDataTask *)task didReceiveResponse:(NSURLResponse *)response completionHandler:(void (^)(NSURLSessionResponseDisposition))handler {
 if(![response isKindOfClass:NSHTTPURLResponse.class] || response.expectedContentLength>2097152) {
   self.oversized=YES;handler(NSURLSessionResponseCancel);return;
 }
 self.response=(NSHTTPURLResponse *)response;handler(NSURLSessionResponseAllow);
}
- (void)URLSession:(NSURLSession *)session dataTask:(NSURLSessionDataTask *)task didReceiveData:(NSData *)data {
 if(self.data.length+data.length>2097152){self.oversized=YES;[task cancel];return;}
 [self.data appendData:data];
}
- (void)URLSession:(NSURLSession *)session task:(NSURLSessionTask *)task willPerformHTTPRedirection:(NSHTTPURLResponse *)response newRequest:(NSURLRequest *)request completionHandler:(void (^)(NSURLRequest *))handler {
 self.redirectSeen=YES;
 NSURLComponents *c=[NSURLComponents componentsWithURL:request.URL resolvingAgainstBaseURL:NO];
 NSString *hostKind=@"other",*pathKind=@"other";
 if([c.host isEqual:@"buy.itunes.apple.com"])hostKind=@"buy";
 else if(c.host.length && [c.host rangeOfString:@"^p[0-9]{1,3}-buy\\.itunes\\.apple\\.com$" options:NSRegularExpressionSearch].location!=NSNotFound)hostKind=@"pod_buy";
 else if([c.host isEqual:@"finance-app.itunes.apple.com"])hostKind=@"finance_app";
 NSDictionary *paths=@{@"/commerce/machine/authorize":@"authorize_exact",@"/commerce/machine/authorize/":@"authorize_slash",
   @"/WebObjects/MZFinance.woa/wa/authorizeMachine":@"legacy",@"/WebObjects/MZFinance.woa/wa/authorizeMachine/":@"legacy_slash"};
 pathKind=paths[c.path]?:@"other";
 BOOL queryOK=c.percentEncodedQuery.length<=2048;
 for(NSURLQueryItem *item in c.queryItems) {
   if([item.name isEqual:@"guid"] && ![item.value.uppercaseString isEqual:self.guid.uppercaseString])queryOK=NO;
   if(([item.name isEqual:@"dsid"] || [item.name isEqual:@"ownerDsid"]) && ![item.value isEqual:self.dsid.stringValue])queryOK=NO;
 }
 self.redirectSummary=@{@"redirect_host_kind":hostKind,@"redirect_path_kind":pathKind,
   @"redirect_query_supported":B(queryOK),@"redirect_method_post":B([request.HTTPMethod isEqual:@"POST"]),
   @"redirect_https":B([c.scheme isEqual:@"https"] && (!c.port || c.port.integerValue==443) && !c.user && !c.password && !c.fragment)};
 BOOL status=response.statusCode==307 || response.statusCode==308;
 NSMutableURLRequest *next=[self.originalRequest mutableCopy];next.URL=request.URL;
 BOOL safe=status && self.redirectCount==0 && [request.HTTPMethod isEqual:@"POST"]
   && ApplySessionHeadersWithRouting(next,self.dsid,self.token,self.guid,YES);
 if(safe){self.cookieCount=ApplyStoreContext(next,self.storeContext);self.redirectCount++;handler(next);return;}
 self.redirected=YES;self.response=response;handler(nil);
}
- (void)URLSession:(NSURLSession *)session task:(NSURLSessionTask *)task didCompleteWithError:(NSError *)error {
 self.error=error;dispatch_semaphore_signal(self.done);
}
@end


static BOOL ApplyClientContext(NSMutableURLRequest *request,NSDictionary *input,NSMutableDictionary *report) {
 id mode=input[@"client_context"];
 if(!mode && !input[@"user_agent"])return YES;
 if(![mode isEqual:@"login_agent"])return NO;
 id agent=input[@"user_agent"];
 if(![agent isKindOfClass:NSString.class] || [agent length]<1 || [agent length]>512
   || [agent rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithRange:NSMakeRange(32,95)] invertedSet]].location!=NSNotFound)return NO;
 NSData *before=[request.HTTPBody copy];
 NSString *previous=[request valueForHTTPHeaderField:@"User-Agent"];
 [request setValue:agent forHTTPHeaderField:@"User-Agent"];
 BOOL bound=[[request valueForHTTPHeaderField:@"User-Agent"] isEqual:agent] && [before isEqual:request.HTTPBody];
 report[@"client_agent_bound"]=B(bound);
 report[@"client_agent_changed"]=B(![previous isEqual:agent]);
 return bound;
}
static BOOL ClientContextContract(void) {
 NSMutableURLRequest *request=[NSMutableURLRequest requestWithURL:[NSURL URLWithString:@"https://buy.itunes.apple.com/commerce/machine/authorize"]];
 request.HTTPMethod=@"POST";request.HTTPBody=[@"synthetic-body" dataUsingEncoding:NSUTF8StringEncoding];
 [request setValue:@"native-fixture/1" forHTTPHeaderField:@"User-Agent"];
 [request setValue:@"synthetic-cookie" forHTTPHeaderField:@"Cookie"];
 NSData *body=[request.HTTPBody copy];NSDictionary *headers=[request.allHTTPHeaderFields copy];
 NSMutableDictionary *report=[NSMutableDictionary dictionary];
 BOOL ok=ApplyClientContext(request,@{},report) && [headers isEqual:request.allHTTPHeaderFields] && report.count==0;
 for(id invalid in @[@"",@"line\r\nInjected: bad",@"control\tvalue",@"non-ascii-\u00e9",@123,[@"x" stringByPaddingToLength:513 withString:@"x" startingAtIndex:0]]) {
   NSMutableURLRequest *copy=[request mutableCopy];
   ok=ok && !ApplyClientContext(copy,@{@"client_context":@"login_agent",@"user_agent":invalid},[NSMutableDictionary dictionary])
     && [copy.allHTTPHeaderFields isEqual:headers] && [copy.HTTPBody isEqual:body];
 }
 ok=ok && !ApplyClientContext([request mutableCopy],@{@"client_context":@"unknown",@"user_agent":@"fixture/1"},[NSMutableDictionary dictionary]);
 ok=ok && !ApplyClientContext([request mutableCopy],@{@"client_context":@"login_agent"},[NSMutableDictionary dictionary]);
 ok=ok && ApplyClientContext(request,@{@"client_context":@"login_agent",@"user_agent":@"login-fixture/1"},report);
 NSMutableDictionary *expected=[headers mutableCopy];expected[@"User-Agent"]=@"login-fixture/1";
 return ok && [report[@"client_agent_bound"] boolValue] && [report[@"client_agent_changed"] boolValue]
   && [request.HTTPBody isEqual:body] && [request.allHTTPHeaderFields isEqual:expected];
}

static NSURLRequest *PreparedRequest(NSDictionary *input,NSMutableDictionary *report) {
 NSString *text=input[@"dsid"],*token=input[@"token"],*guid=input[@"guid"];
 if(![text isKindOfClass:NSString.class] || [text rangeOfString:@"^[1-9][0-9]{0,17}$" options:NSRegularExpressionSearch].location==NSNotFound)return nil;
 NSNumber *dsid=@(text.longLongValue);
 Class ac=NSClassFromString(@"ACAccount");SEL create=NSSelectorFromString(@"ams_createEphemeralAccount");
 if(!ABI(ac,create,@"@",@[]))return nil;
 id account=((id(*)(id,SEL))objc_msgSend)(ac,create);
 SEL ep=NSSelectorFromString(@"ams_isEphemeralAccount");
 if(!(ABI(account,ep,@"B",@[])||ABI(account,ep,@"c",@[])))return nil;
 if(!((BOOL(*)(id,SEL))objc_msgSend)(account,ep))return nil;
 report[@"ephemeral_account"]=@YES;
 SEL setDSID=NSSelectorFromString(@"ams_setDSID:");if(!ABI(account,setDSID,@"v",@[@"@"]))return nil;
 ((void(*)(id,SEL,id))objc_msgSend)(account,setDSID,dsid);
 Class cls=NSClassFromString(@"AMSAuthorizeMachineTask");SEL bagSel=NSSelectorFromString(@"createBagForSubProfile");
 if(!ABI(cls,bagSel,@"@",@[]))return nil;
 id bag=((id(*)(id,SEL))objc_msgSend)(cls,bagSel);
 id task=[cls alloc];SEL init=NSSelectorFromString(@"initWithAccount:authorizeReason:bag:");
 if(!ABI(task,init,@"@",@[@"@",@"Q",@"@"]))return nil;
 task=((id(*)(id,SEL,id,unsigned long long,id))objc_msgSend)(task,init,account,0,bag);
 SEL build=NSSelectorFromString(@"_buildRequest");if(!ABI(task,build,@"@",@[]))return nil;
 id promise=((id(*)(id,SEL))objc_msgSend)(task,build);SEL resultSel=NSSelectorFromString(@"resultWithTimeout:error:");
 if(!ABI(promise,resultSel,@"@",@[@"d",@"^@"]))return nil;
 NSError *error=nil;
 id value=((id(*)(id,SEL,double,NSError *__autoreleasing *))objc_msgSend)(promise,resultSel,15.0,&error);
 ErrorFields(report,error);
 if(error || ![value isKindOfClass:NSURLRequest.class])return nil;
 NSMutableURLRequest *request=[value mutableCopy];
 BOOL valid=ApplySessionHeaders(request,dsid,token,guid);
 NSDictionary *boundBody=request.HTTPBody?[NSPropertyListSerialization propertyListWithData:request.HTTPBody options:NSPropertyListImmutable format:NULL error:NULL]:nil;
 BOOL bound=[boundBody isKindOfClass:NSDictionary.class] && [boundBody[@"xToken"] isEqual:token]
   && [[request valueForHTTPHeaderField:@"Content-Length"] longLongValue]==(long long)request.HTTPBody.length;
 report[@"body_token_bound"]=B(valid && bound);
 valid=valid && bound;
 report[@"session_identity_verified"]=B(valid);
 if(!valid)return nil;
 report[@"session_cookie_count"]=@(ApplyStoreContext(request,input));
 report[@"storefront_header_present"]=B([request valueForHTTPHeaderField:@"X-Apple-Store-Front"].length>0);
 if(!ApplyClientContext(request,input,report))return nil;
 request.timeoutInterval=30;
 return request;
}

static void ImportErrorFields(NSMutableDictionary *report,NSError *error) {
 if(![error.domain isEqual:@"AMSErrorDomain"] || error.code!=505)return;
 NSString *reason=error.localizedFailureReason;
 if(![reason isKindOfClass:NSString.class] || reason.length>128)return;
 NSRegularExpression *pattern=[NSRegularExpression regularExpressionWithPattern:@"^Import error with status: (-?[0-9]{1,10})$" options:0 error:NULL];
 NSTextCheckingResult *match=[pattern firstMatchInString:reason options:0 range:NSMakeRange(0,reason.length)];
 if(!match)return;
 long long status=[[reason substringWithRange:[match rangeAtIndex:1]] longLongValue];
 if(status>=INT32_MIN && status<=INT32_MAX)report[@"import_fairplay_status"]=@(status);
}
static BOOL ImportErrorContract(void) {
 NSMutableDictionary *report=[NSMutableDictionary dictionary];
 NSError *error=[NSError errorWithDomain:@"AMSErrorDomain" code:505 userInfo:@{
   NSLocalizedDescriptionKey:@"PRIVATE_DESCRIPTION",NSLocalizedFailureReasonErrorKey:@"Import error with status: -42000"}];
 ImportErrorFields(report,error);
 if(![report isEqual:@{@"import_fairplay_status":@(-42000)}])return NO;
 for(NSString *reason in @[@"PRIVATE_REASON",@"Import error with status: 9999999999",@"Import error with status: -42000 PRIVATE", @"Import error with status: 1234567890123"]) {
   NSMutableDictionary *bad=[NSMutableDictionary dictionary];
   ImportErrorFields(bad,[NSError errorWithDomain:@"AMSErrorDomain" code:505 userInfo:@{NSLocalizedFailureReasonErrorKey:reason}]);
   if(bad.count)return NO;
 }
 for(NSError *other in @[
   [NSError errorWithDomain:@"OTHER_PRIVATE" code:505 userInfo:@{NSLocalizedFailureReasonErrorKey:@"Import error with status: -42000"}],
   [NSError errorWithDomain:@"AMSErrorDomain" code:500 userInfo:@{NSLocalizedFailureReasonErrorKey:@"Import error with status: -42000"}]]) {
   NSMutableDictionary *bad=[NSMutableDictionary dictionary];ImportErrorFields(bad,other);if(bad.count)return NO;
 }
 return YES;
}
static unsigned int ContextIdentifier(id bag) {
 SEL context=NSSelectorFromString(@"fairplayContextWithError:");
 if(!ABI(bag,context,@"I",@[@"^@"]))return 0;
 NSError *error=nil;
 unsigned int value=((unsigned int(*)(id,SEL,NSError *__autoreleasing *))objc_msgSend)(bag,context,&error);
 return error?0:value;
}
static id SharedKeybag(void) {
 Class cls=NSClassFromString(@"AMSKeybag");SEL shared=NSSelectorFromString(@"sharedInstance");
 return ABI(cls,shared,@"@",@[])?((id(*)(id,SEL))objc_msgSend)(cls,shared):nil;
}
static void InvalidImportProbe(NSMutableDictionary *r) {
 r[@"status"]=@"import_interface_unavailable";r[@"state_before"]=State();
 id bag=SharedKeybag();unsigned int context=ContextIdentifier(bag);
 r[@"context_ready_before_request"]=B(context!=0);
 SEL import=NSSelectorFromString(@"importKeybagWithData:error:");
 if(!(ABI(bag,import,@"B",@[@"@",@"^@"])||ABI(bag,import,@"c",@[@"@",@"^@"])))return;
 NSData *invalid=[@"ipa-lab-invalid-keybag" dataUsingEncoding:NSUTF8StringEncoding];
 NSError *error=nil;
 BOOL ok=((BOOL(*)(id,SEL,id,NSError *__autoreleasing *))objc_msgSend)(bag,import,invalid,&error);
 ErrorFields(r,error);ImportErrorFields(r,error);
 r[@"expected_invalid_keybag_rejected"]=B(!ok && error!=nil);
 r[@"context_stable_after_rejection"]=B(context!=0 && context==ContextIdentifier(bag));
 r[@"status"]=!ok && error?@"invalid_keybag_rejected":@"invalid_keybag_unexpected_result";
}

static void Authorize(NSDictionary *input,NSMutableDictionary *r) {
 r[@"state_before"]=State();
 id initialKeybag=SharedKeybag();unsigned int initialContext=ContextIdentifier(initialKeybag);
 r[@"context_ready_before_request"]=B(initialContext!=0);
 NSURLRequest *request=PreparedRequest(input,r);
 if(!request){r[@"status"]=@"request_preparation_failed";return;}
 LabEnrollmentResponse *delegate=[LabEnrollmentResponse new];
 delegate.originalRequest=request;delegate.dsid=@([input[@"dsid"] longLongValue]);
 delegate.token=input[@"token"];delegate.guid=input[@"guid"];delegate.storeContext=input;
 delegate.cookieCount=[r[@"session_cookie_count"] unsignedIntegerValue];
 NSURLSessionConfiguration *config=[NSURLSessionConfiguration ephemeralSessionConfiguration];
 config.URLCache=nil;config.HTTPCookieStorage=nil;config.URLCredentialStorage=nil;
 config.HTTPShouldSetCookies=NO;config.timeoutIntervalForRequest=30;config.timeoutIntervalForResource=40;
 NSOperationQueue *queue=[NSOperationQueue new];queue.maxConcurrentOperationCount=1;
 NSURLSession *session=[NSURLSession sessionWithConfiguration:config delegate:delegate delegateQueue:queue];
 NSURLSessionDataTask *task=[session dataTaskWithRequest:request];
 r[@"authorization_request_attempted"]=@YES;
 [task resume];
 BOOL done=dispatch_semaphore_wait(delegate.done,dispatch_time(DISPATCH_TIME_NOW,45*NSEC_PER_SEC))==0;
 [session invalidateAndCancel];
 if(!done){r[@"status"]=@"request_timeout";return;}
 r[@"session_cookie_count"]=@(delegate.cookieCount);
 if(delegate.redirectSummary)[r addEntriesFromDictionary:delegate.redirectSummary];
 r[@"redirect_seen"]=B(delegate.redirectSeen);r[@"approved_redirect_count"]=@(delegate.redirectCount);
 r[@"redirect_blocked"]=B(delegate.redirected);r[@"response_oversized"]=B(delegate.oversized);
 if(delegate.response){r[@"http_status"]=@(delegate.response.statusCode);[r addEntriesFromDictionary:AnisetteResponseFields(delegate.response)];}
 ErrorFields(r,delegate.error);
 if(delegate.redirected || delegate.oversized || delegate.error){r[@"status"]=@"request_stopped";return;}
 id obj=[NSPropertyListSerialization propertyListWithData:delegate.data options:NSPropertyListImmutable format:NULL error:NULL];
 if(![obj isKindOfClass:NSDictionary.class]){r[@"status"]=@"response_not_plist";return;}
 NSDictionary *body=obj;
 id failure=body[@"failureType"];
 BOOL hasFailure=failure && ![failure isEqual:@""] && ![failure isEqual:@0] && ![failure isEqual:@"0"];
 r[@"apple_failure_present"]=B(hasFailure);
 if([failure isKindOfClass:NSString.class] && [failure rangeOfString:@"^-?[0-9]{1,6}$" options:NSRegularExpressionSearch].location!=NSNotFound)r[@"apple_failure_code"]=@([failure integerValue]);
 r[@"dialog_present"]=B(body[@"dialog"]!=nil || body[@"dialogTitle"]!=nil);
 NSMutableArray *messages=[NSMutableArray array];
 for(NSString *key in @[@"customerMessage",@"dialogTitle"])if([body[key] isKindOfClass:NSString.class])[messages addObject:body[key]];
 if([body[@"dialog"] isKindOfClass:NSDictionary.class])for(NSString *key in @[@"explanation",@"message",@"title"])
   if([body[@"dialog"][key] isKindOfClass:NSString.class])[messages addObject:body[@"dialog"][key]];
 NSString *message=[[messages componentsJoinedByString:@" "] lowercaseString];
 if(message.length<8192) {
   r[@"message_mentions_sign_in"]=B([message containsString:@"sign in"] || [message containsString:@"sign-in"]);
   r[@"message_mentions_password"]=B([message containsString:@"password"]);
   r[@"message_mentions_verification_code"]=B([message containsString:@"verification code"]);
   r[@"message_mentions_computer_limit"]=B([message containsString:@"five computers"] || [message containsString:@"5 computers"]);
 }
 id blob=body[@"keybag"];
 BOOL keybag=[blob isKindOfClass:NSData.class] && [blob length]>0 && [blob length]<=2097152;
 r[@"keybag_present"]=B(keybag);
 if(delegate.response.statusCode!=200 || hasFailure || !keybag) {r[@"status"]=@"keybag_not_issued";return;}
 Class cls=NSClassFromString(@"AMSKeybag");SEL shared=NSSelectorFromString(@"sharedInstance");
 if(!ABI(cls,shared,@"@",@[])){r[@"status"]=@"import_interface_unavailable";return;}
 id bag=((id(*)(id,SEL))objc_msgSend)(cls,shared);SEL import=NSSelectorFromString(@"importKeybagWithData:error:");
 if(!(ABI(bag,import,@"B",@[@"@",@"^@"]) || ABI(bag,import,@"c",@[@"@",@"^@"]))) {
   r[@"status"]=@"import_interface_unavailable";return;
 }
 r[@"context_stable_before_import"]=B(initialContext!=0 && initialKeybag==bag && initialContext==ContextIdentifier(bag));
 NSError *error=nil;
 BOOL imported=((BOOL(*)(id,SEL,id,NSError *__autoreleasing *))objc_msgSend)(bag,import,blob,&error);
 ErrorFields(r,error);ImportErrorFields(r,error);r[@"keybag_import_succeeded"]=B(imported && !error);
 r[@"status"]=imported && !error?@"keybag_imported_model_unverified":@"keybag_import_failed";
}
int main(int argc,const char **argv) { @autoreleasepool {
 if((argc!=2 && argc!=3) || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 if(!strcmp(argv[1],"--response-contract")) {
   BOOL ok=ResponseContract() && ClientContextContract() && ImportErrorContract();puts(ok?"response and client context contracts passed":"response and client context contracts failed");return ok?0:4;
 }
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-machine-enrollment-v1",@"status":@"invalid_private_input",
   @"authorization_request_attempted":@NO,@"enrollment_created":@NO,@"decryption_proven":@NO} mutableCopy];
 @try {
   dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL);
   dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL);
   if(argc==3 && !strcmp(argv[1],"--import-probe")) {
     InvalidImportProbe(r);
   } else if(argc==2) {
     NSData *data=[[NSFileHandle fileHandleWithStandardInput] readDataOfLength:65537];
     id input=data.length<=65536?[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL]:nil;
     if([input isKindOfClass:NSDictionary.class])Authorize(input,r);
   }
 } @catch(NSException *e) {r[@"status"]=@"native_exception";}
 r[@"state_after"]=State();
 NSData *report=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return report && [report writeToFile:@(argv[argc==3?2:1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
