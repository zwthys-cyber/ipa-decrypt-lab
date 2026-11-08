@testable import ApplePackage
import Foundation
import XCTest
import ObjectiveC
import Darwin

final class LabStoreAMDTransportTests: XCTestCase {
    func testPublicBagRoutingStripsAccountHeadersAndKeepsPublicTLSOrigin() {
        let input = NSMutableURLRequest(url: URL(string:"https://bag.itunes.apple.com/bag.xml?private=synthetic")!)
        input.httpMethod = "GET"
        URLProtocol.setProperty("synthetic-routing-context", forKey:"LabNativeContext", in:input)
        input.setValue("synthetic-cookie", forHTTPHeaderField:"Cookie")
        input.setValue("synthetic-token", forHTTPHeaderField:"Authorization")
        let output = StoreAMD.publicBagRequest(input)
        XCTAssertEqual(output.url?.absoluteString,"https://init.itunes.apple.com/bag.xml?ix=6")
        XCTAssertEqual(URLProtocol.property(forKey:"LabNativeContext", in:output as URLRequest) as? String,"synthetic-routing-context")
        XCTAssertNil(output.value(forHTTPHeaderField:"Cookie"))
        XCTAssertNil(output.value(forHTTPHeaderField:"Authorization"))
        XCTAssertEqual(input.value(forHTTPHeaderField:"Cookie"),"synthetic-cookie")
    }
    func testAccountAndUntrustedRequestsAreNeverRerouted() {
        for raw in ["https://auth.itunes.apple.com/auth/v1/native", "https://bag.itunes.apple.com.evil.invalid/bag.xml", "http://bag.itunes.apple.com/bag.xml", "https://user@bag.itunes.apple.com/bag.xml", "https://bag.itunes.apple.com:8443/bag.xml", "https://bag.itunes.apple.com/other", "https://bag.itunes.apple.com/bag.xml#x"] {
            let input = NSURLRequest(url:URL(string:raw)!)
            XCTAssertTrue(StoreAMD.publicBagRequest(input) === input)
        }
        let post = NSMutableURLRequest(url:URL(string:"https://bag.itunes.apple.com/bag.xml")!)
        post.httpMethod = "POST"
        XCTAssertTrue(StoreAMD.publicBagRequest(post) === post)
    }
    func testCommerceProofsAreBoundToExactEndpoints() {
        for raw in ["https://buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/buyProduct", "https://p25-buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/buyProduct", "https://downloaddispatch.itunes.apple.com/WebObjects/DownloadDispatch.woa/wa/ent/download?guid=synthetic"] {
            XCTAssertTrue(StoreAMD.commerceApproved(URL(string:raw)!))
        }
        for raw in ["https://buy.itunes.apple.com.evil.invalid/WebObjects/MZFinance.woa/wa/buyProduct", "https://evil-buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/buyProduct", "https://buy.itunes.apple.com/other", "http://buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/buyProduct", "https://user@downloaddispatch.itunes.apple.com/WebObjects/DownloadDispatch.woa/wa/ent/download", "https://downloaddispatch.itunes.apple.com:8443/WebObjects/DownloadDispatch.woa/wa/ent/download", "https://downloaddispatch.itunes.apple.com/WebObjects/DownloadDispatch.woa/wa/ent%2fdownload"] {
            XCTAssertFalse(StoreAMD.commerceApproved(URL(string:raw)!))
        }
    }
    func testOnlyNativeRetryActionWithoutErrorCanRepeatLogin() throws {
        _ = dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices",RTLD_NOW|RTLD_LOCAL)
        let cls = try XCTUnwrap(NSClassFromString("AMSURLAction"))
        typealias Create = @convention(c) (AnyObject,Selector) -> Unmanaged<AnyObject>?
        func action(_ name:String) throws -> NSObject {
            let sel = NSSelectorFromString(name), method = try XCTUnwrap(class_getClassMethod(cls,sel))
            return try XCTUnwrap(unsafeBitCast(method_getImplementation(method),to:Create.self)(cls as AnyObject,sel)?.takeUnretainedValue() as? NSObject)
        }
        XCTAssertTrue(StoreAMD.retryAction(try action("retryAction")))
        XCTAssertFalse(StoreAMD.retryAction(try action("proceedAction")))
        let sel = NSSelectorFromString("actionWithError:"), method = try XCTUnwrap(class_getClassMethod(cls,sel))
        typealias Failure = @convention(c) (AnyObject,Selector,AnyObject) -> Unmanaged<AnyObject>?
        let error = NSError(domain:"SyntheticStoreFailure",code:1)
        let failed = try XCTUnwrap(unsafeBitCast(method_getImplementation(method),to:Failure.self)(cls as AnyObject,sel,error)?.takeUnretainedValue() as? NSObject)
        XCTAssertFalse(StoreAMD.retryAction(failed))
        XCTAssertFalse(StoreAMD.retryAction(NSObject()))
    }
}
