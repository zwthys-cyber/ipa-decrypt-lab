// One public synthetic constructor; no URLSession task or authorization call.
#include "CNEnrollmentConstructor.inc"
int main(int argc,const char **argv) { @autoreleasepool {
 if(argc!=2 || !getenv("GITHUB_ACTIONS") || strcmp(getenv("GITHUB_ACTIONS"),"true"))return 2;
 signal(SIGALRM,LabNativeDeadline);alarm(45);
 NSMutableDictionary *report=[@{@"schema":@"cn-storefront-contract-v1",@"status":@"constructor_unavailable",
   @"account_login_attempted":@NO,@"authorization_request_attempted":@NO,@"model_recovered":@NO} mutableCopy];
 @try {
  dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_GLOBAL);
  dlopen("/System/Library/Frameworks/Accounts.framework/Accounts",RTLD_NOW|RTLD_GLOBAL);
  NSData *raw=[[NSFileHandle fileHandleWithStandardInput] readDataOfLength:4097];
  id value=raw.length<=4096?[NSJSONSerialization JSONObjectWithData:raw options:0 error:NULL]:nil;
  NSString *guid=[value isKindOfClass:NSDictionary.class]?value[@"guid"]:nil;
  if([guid isKindOfClass:NSString.class] && [guid rangeOfString:@"^[A-F0-9]{12}$" options:NSRegularExpressionSearch].location!=NSNotFound) {
   NSDictionary *input=@{@"dsid":@"1234567",@"token":@"fixed-synthetic-not-a-token",@"guid":guid,
     @"client_context":@"login_agent",@"user_agent":@"Configurator/2.21 (Macintosh; Intel Mac OS X 15.0)",@"backend":@"commerce",@"apple_id":@"ipa-lab@example.invalid",@"cookies":@[]};
   NSMutableDictionary *construction=[NSMutableDictionary dictionary];LabCommerceRun *context=nil;
   NSMutableURLRequest *request=PreparedCommerceSession(input,construction,&context);
   if(request) {
    NSString *front=[request valueForHTTPHeaderField:@"X-Apple-Store-Front"];
    NSString *country=!front.length?@"absent":[front hasPrefix:@"143465-"]?@"cn":[front hasPrefix:@"143441-"]?@"us":[front hasPrefix:@"143443-"]?@"de":@"other";
    report[@"default_country"]=country;
    NSData *body=[request.HTTPBody copy];NSString *md=[request valueForHTTPHeaderField:@"X-Apple-I-MD"],*mdm=[request valueForHTTPHeaderField:@"X-Apple-I-MD-M"];
    NSDictionary *bodyBefore=[NSPropertyListSerialization propertyListWithData:body options:NSPropertyListImmutable format:NULL error:NULL];
    NSMutableDictionary *bound=[input mutableCopy];bound[@"storefront"]=@"143465-19,32";ApplyStoreContext(request,bound);
    report[@"cn_override_bound"]=B([[request valueForHTTPHeaderField:@"X-Apple-Store-Front"] isEqual:@"143465-19,32"]);
    report[@"body_preserved"]=B([body isEqual:request.HTTPBody]);
    report[@"native_guid_preserved"]=B([bodyBefore[@"guid"] isEqual:guid]);
    report[@"anisette_preserved"]=B(((!md && ![request valueForHTTPHeaderField:@"X-Apple-I-MD"]) || [md isEqual:[request valueForHTTPHeaderField:@"X-Apple-I-MD"]]) && ((!mdm && ![request valueForHTTPHeaderField:@"X-Apple-I-MD-M"]) || [mdm isEqual:[request valueForHTTPHeaderField:@"X-Apple-I-MD-M"]]));
    report[@"status"]=@"constructor_observed";
   }
  }
 } @catch(NSException *error) {report[@"status"]=@"constructor_unavailable";}
 NSData *data=[NSJSONSerialization dataWithJSONObject:report options:0 error:NULL];
 return data && [data writeToFile:@(argv[1]) options:NSDataWritingAtomic error:NULL]?0:3;
}}
