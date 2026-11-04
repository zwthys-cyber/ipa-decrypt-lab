// One machine-authorization request using an existing private Store session.
// Reuse audited ABI, state-report, and destination/identity checks.
#define main KeybagPrerequisitesMain
#include "NativeKeybag.m"
#undef main

@interface LabEnrollmentResponse : NSObject <NSURLSessionDataDelegate>
@property(nonatomic,strong) NSMutableData *data;
@property(nonatomic,strong) NSHTTPURLResponse *response;
@property(nonatomic,strong) NSError *error;
@property(nonatomic) BOOL redirected;
@property(nonatomic) BOOL redirectSeen;
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
 BOOL status=response.statusCode==307 || response.statusCode==308;
 NSMutableURLRequest *next=[self.originalRequest mutableCopy];next.URL=request.URL;
 BOOL safe=status && self.redirectCount==0 && [request.HTTPMethod isEqual:@"POST"]
   && ApplySessionHeadersWithRouting(next,self.dsid,self.token,self.guid,YES);
 if(safe){self.redirectCount++;handler(next);return;}
 self.redirected=YES;self.response=response;handler(nil);
}
- (void)URLSession:(NSURLSession *)session task:(NSURLSessionTask *)task didCompleteWithError:(NSError *)error {
 self.error=error;dispatch_semaphore_signal(self.done);
}
@end

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
 report[@"session_identity_verified"]=B(valid);
 if(!valid)return nil;
 request.timeoutInterval=30;
 return request;
}
static void Authorize(NSDictionary *input,NSMutableDictionary *r) {
 r[@"state_before"]=State();
 NSURLRequest *request=PreparedRequest(input,r);
 if(!request){r[@"status"]=@"request_preparation_failed";return;}
 LabEnrollmentResponse *delegate=[LabEnrollmentResponse new];
 delegate.originalRequest=request;delegate.dsid=@([input[@"dsid"] longLongValue]);
 delegate.token=input[@"token"];delegate.guid=input[@"guid"];
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
 r[@"redirect_seen"]=B(delegate.redirectSeen);r[@"approved_redirect_count"]=@(delegate.redirectCount);
 r[@"redirect_blocked"]=B(delegate.redirected);r[@"response_oversized"]=B(delegate.oversized);
 if(delegate.response)r[@"http_status"]=@(delegate.response.statusCode);
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
 NSError *error=nil;
 BOOL imported=((BOOL(*)(id,SEL,id,NSError *__autoreleasing *))objc_msgSend)(bag,import,blob,&error);
 ErrorFields(r,error);r[@"keybag_import_succeeded"]=B(imported && !error);
 r[@"status"]=imported && !error?@"keybag_imported_model_unverified":@"keybag_import_failed";
}
int main(int argc,const char **argv) { @autoreleasepool {
 if(argc!=2 || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 NSMutableDictionary *r=[@{@"schema":@"ipa-lab-machine-enrollment-v1",@"status":@"invalid_private_input",
   @"authorization_request_attempted":@NO,@"enrollment_created":@NO,@"decryption_proven":@NO} mutableCopy];
 @try {
   NSData *data=[[NSFileHandle fileHandleWithStandardInput] readDataOfLength:65537];
   id input=data.length<=65536?[NSJSONSerialization JSONObjectWithData:data options:0 error:NULL]:nil;
   if([input isKindOfClass:NSDictionary.class]) {
     dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL);
     dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL);
     Authorize(input,r);
   }
 } @catch(NSException *e) {r[@"status"]=@"native_exception";}
 r[@"state_after"]=State();
 NSData *report=[NSJSONSerialization dataWithJSONObject:r options:0 error:NULL];
 return report && [report writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
