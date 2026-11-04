// Private in-memory binding; never rewrites a mismatched identity or sends a request.
#import <Foundation/Foundation.h>
static BOOL LabCommerceRoute(NSURLRequest *request,NSString *guid) {
 if(![request isKindOfClass:NSURLRequest.class] || ![request.HTTPMethod isEqual:@"POST"]
   || request.HTTPBodyStream || request.HTTPBody.length==0 || request.HTTPBody.length>1048576)return NO;
 NSURLComponents *url=[NSURLComponents componentsWithURL:request.URL resolvingAgainstBaseURL:NO];
 if(![url.scheme isEqual:@"https"] || ![url.host isEqual:@"buy.itunes.apple.com"]
   || ![url.path isEqual:@"/commerce/machine/authorize"] || url.user || url.password || url.fragment
   || (url.port && url.port.integerValue!=443) || url.percentEncodedQuery.length>2048)return NO;
 NSUInteger count=0;
 for(NSURLQueryItem *item in url.queryItems) {
   if(![item.name isEqual:@"guid"] || ++count>1 || ![item.value.uppercaseString isEqual:guid.uppercaseString])return NO;
 }
 return YES;
}
static NSMutableURLRequest *LabBindCommerceSession(NSURLRequest *source,NSNumber *dsid,NSString *token,NSString *guid,NSString *agent) {
 if(![dsid isKindOfClass:NSNumber.class] || CFGetTypeID((__bridge CFTypeRef)dsid)==CFBooleanGetTypeID()
   || dsid.longLongValue<=0 || dsid.longLongValue>999999999999999999LL
   || ![token isKindOfClass:NSString.class] || token.length==0 || token.length>8192 || [token isEqual:@"0"]
   || [token rangeOfCharacterFromSet:NSCharacterSet.controlCharacterSet].location!=NSNotFound
   || ![guid isKindOfClass:NSString.class] || [guid rangeOfString:@"^[A-Fa-f0-9]{12}$" options:NSRegularExpressionSearch].location==NSNotFound
   || ![agent isKindOfClass:NSString.class] || !agent.length || agent.length>512
   || [agent rangeOfCharacterFromSet:[[NSCharacterSet characterSetWithRange:NSMakeRange(32,95)] invertedSet]].location!=NSNotFound
   || !LabCommerceRoute(source,guid) || [source valueForHTTPHeaderField:@"X-Apple-ActionSignature"].length)return nil;
 id parsed=[NSPropertyListSerialization propertyListWithData:source.HTTPBody options:NSPropertyListImmutable format:NULL error:NULL];
 if(![parsed isKindOfClass:NSDictionary.class])return nil;
 NSDictionary *body=parsed;
 id nativeGUID=body[@"guid"],owner=body[@"ownerDsid"],sync=body[@"kbsync"],needDiv=body[@"needDiv"];
 if(![nativeGUID isKindOfClass:NSString.class] || ![nativeGUID isEqual:guid.uppercaseString]
   || (owner && ![owner isEqual:dsid] && ![owner isEqual:dsid.stringValue])
   || ![body[@"xToken"] isEqual:token] || ![sync isKindOfClass:NSString.class]
   || (![needDiv isEqual:@"0"] && ![needDiv isEqual:@"1"]))return nil;
 NSData *bytes=[[NSData alloc] initWithBase64EncodedString:sync options:0];
 if(!bytes.length || bytes.length>1048576)return nil;
 for(NSString *name in @[@"X-Dsid",@"iCloud-DSID",@"X-Token"]) {
   NSString *existing=[source valueForHTTPHeaderField:name];
   NSString *expected=[name isEqual:@"X-Token"]?token:dsid.stringValue;
   if(existing && ![existing isEqual:expected])return nil;
 }
 NSMutableDictionary *boundBody=[body mutableCopy];boundBody[@"ownerDsid"]=dsid;
 NSData *encoded=[NSPropertyListSerialization dataWithPropertyList:boundBody format:NSPropertyListXMLFormat_v1_0 options:0 error:NULL];
 if(!encoded.length || encoded.length>1048576)return nil;
 NSMutableURLRequest *request=[source mutableCopy];request.HTTPBody=encoded;
 [request setValue:[NSString stringWithFormat:@"%lu",(unsigned long)encoded.length] forHTTPHeaderField:@"Content-Length"];
 [request setValue:dsid.stringValue forHTTPHeaderField:@"X-Dsid"];
 [request setValue:dsid.stringValue forHTTPHeaderField:@"iCloud-DSID"];
 [request setValue:token forHTTPHeaderField:@"X-Token"];
 [request setValue:agent forHTTPHeaderField:@"User-Agent"];
 [request setValue:nil forHTTPHeaderField:@"Cookie"];
 return request;
}
static BOOL LabCommerceBindingContract(void) {
 NSString *guid=@"001122334455",*token=@"fixed-token",*agent=@"Configurator/fixed";
 NSDictionary *body=@{@"guid":guid,@"kbsync":@"AQIDBA==",@"needDiv":@"1",@"xToken":token};
 NSMutableURLRequest *source=[NSMutableURLRequest requestWithURL:[NSURL URLWithString:@"https://buy.itunes.apple.com/commerce/machine/authorize?guid=001122334455"]];
 source.HTTPMethod=@"POST";
 source.HTTPBody=[NSPropertyListSerialization dataWithPropertyList:body format:NSPropertyListXMLFormat_v1_0 options:0 error:NULL];
 [source setValue:@"fixed-cookie" forHTTPHeaderField:@"Cookie"];
 [source setValue:@"fixed-anisette" forHTTPHeaderField:@"X-Apple-I-MD"];
 NSURLRequest *original=[source copy];
 NSMutableURLRequest *bound=LabBindCommerceSession(source,@1234567,token,guid,agent);
 NSDictionary *result=bound?[NSPropertyListSerialization propertyListWithData:bound.HTTPBody options:NSPropertyListImmutable format:NULL error:NULL]:nil;
 BOOL ok=bound && [result[@"ownerDsid"] isEqual:@1234567] && [result[@"guid"] isEqual:guid]
   && [result[@"kbsync"] isEqual:body[@"kbsync"]] && [result[@"xToken"] isEqual:token]
   && [result[@"needDiv"] isEqual:@"1"] && [[bound valueForHTTPHeaderField:@"User-Agent"] isEqual:agent]
   && [[bound valueForHTTPHeaderField:@"X-Dsid"] isEqual:@"1234567"]
   && [[bound valueForHTTPHeaderField:@"iCloud-DSID"] isEqual:@"1234567"]
   && [[bound valueForHTTPHeaderField:@"X-Token"] isEqual:token]
   && [[bound valueForHTTPHeaderField:@"Content-Length"] longLongValue]==(long long)bound.HTTPBody.length
   && ![bound valueForHTTPHeaderField:@"Cookie"] && [[bound valueForHTTPHeaderField:@"X-Apple-I-MD"] isEqual:@"fixed-anisette"];
 for(NSString *bad in @[@"",@"0",@"bad\r\nInjected: value"])
   ok=ok && LabBindCommerceSession(source,@1234567,bad,guid,agent)==nil;
 for(NSString *bad in @[@"",@"bad\nAgent",@"non-ascii-é"])
   ok=ok && LabBindCommerceSession(source,@1234567,token,guid,bad)==nil;
 ok=ok && !LabBindCommerceSession(source,@YES,token,guid,agent)
   && !LabBindCommerceSession(source,@0,token,guid,agent)
   && !LabBindCommerceSession(source,@1234567,token,@"001122334466",agent);
 for(NSString *badURL in @[@"http://buy.itunes.apple.com/commerce/machine/authorize",
   @"https://example.invalid/commerce/machine/authorize",@"https://buy.itunes.apple.com/other",
   @"https://user:pass@buy.itunes.apple.com/commerce/machine/authorize",
   @"https://buy.itunes.apple.com:444/commerce/machine/authorize",
   @"https://buy.itunes.apple.com/commerce/machine/authorize?guid=001122334466",
   @"https://buy.itunes.apple.com/commerce/machine/authorize?guid=001122334455&guid=001122334455",
   @"https://buy.itunes.apple.com/commerce/machine/authorize?other=value",
   @"https://buy.itunes.apple.com/commerce/machine/authorize#fragment"]) {
   NSMutableURLRequest *bad=[source mutableCopy];bad.URL=[NSURL URLWithString:badURL];
   ok=ok && !LabBindCommerceSession(bad,@1234567,token,guid,agent);
 }
 for(NSString *header in @[@"X-Dsid",@"iCloud-DSID",@"X-Token",@"X-Apple-ActionSignature"]) {
   NSMutableURLRequest *bad=[source mutableCopy];[bad setValue:@"conflicting-value" forHTTPHeaderField:header];
   ok=ok && !LabBindCommerceSession(bad,@1234567,token,guid,agent);
 }
 for(NSString *key in @[@"ownerDsid",@"guid",@"xToken",@"kbsync",@"needDiv"]) {
   NSMutableDictionary *badBody=[body mutableCopy];badBody[key]=@"conflicting-value";
   NSMutableURLRequest *bad=[source mutableCopy];
   bad.HTTPBody=[NSPropertyListSerialization dataWithPropertyList:badBody format:NSPropertyListXMLFormat_v1_0 options:0 error:NULL];
   ok=ok && !LabBindCommerceSession(bad,@1234567,token,guid,agent);
 }
 NSMutableURLRequest *bad=[source mutableCopy];bad.HTTPMethod=@"GET";
 ok=ok && !LabBindCommerceSession(bad,@1234567,token,guid,agent);
 return ok && [source isEqual:original];
}
