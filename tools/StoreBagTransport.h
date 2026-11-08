#ifdef __OBJC__
#import <Foundation/Foundation.h>
NS_ASSUME_NONNULL_BEGIN
@interface LabStoreBagTransport : NSObject
+ (BOOL)install;
+ (nullable id)nativeBag;
+ (NSURLRequest *)publicRequest:(NSURLRequest *)request;
@end
NS_ASSUME_NONNULL_END
#endif
