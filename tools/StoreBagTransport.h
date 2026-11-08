#ifdef __OBJC__
#import <Foundation/Foundation.h>
@interface LabStoreBagTransport : NSObject
+ (BOOL)install;
+ (NSURLRequest *)publicRequest:(NSURLRequest *)request;
@end
#endif
