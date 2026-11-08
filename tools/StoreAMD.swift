import Foundation
import CApplePackage
import ObjectiveC
import Darwin

// Only Apple's public bag request is rerouted. The native parser retains the
// complete trustedDomains policy. Account requests and proof values stay private.
enum StoreAMD {
    private static let transportReady = LabStoreBagTransport.install()

    static func publicBagRequest(_ request: NSURLRequest) -> NSURLRequest {
        let updated = LabStoreBagTransport.publicRequest(request as URLRequest)
        return updated == request as URLRequest ? request : updated as NSURLRequest
    }

    private static func bag() throws -> AnyObject {
        guard transportReady, let value = LabStoreBagTransport.nativeBag() else { throw NSError(domain:"StoreAMD",code:3) }
        return value as AnyObject
    }

    static func resolved(_ value: AnyObject) -> AnyObject? {
        let selector = NSSelectorFromString("resultWithError:")
        guard let method = class_getInstanceMethod(object_getClass(value), selector) else { return value }
        typealias Wait = @convention(c) (AnyObject, Selector, UnsafeMutableRawPointer?) -> Unmanaged<AnyObject>?
        let call = unsafeBitCast(method_getImplementation(method), to: Wait.self)
        return call(value, selector, nil)?.takeUnretainedValue()
    }

    static func headers(for endpoint: URL) throws -> [(String, String)] {
        _ = try Authenticator.approvedEndpoint(endpoint)
        guard endpoint.host?.lowercased() == "auth.itunes.apple.com" else { return [] }
        return try proofHeaders(endpoint, required: false)
    }

    static func commerceApproved(_ endpoint: URL) -> Bool {
        guard let p = URLComponents(url: endpoint, resolvingAgainstBaseURL: false), p.scheme == "https",
              p.user == nil, p.password == nil, p.fragment == nil, p.port == nil || p.port == 443,
              let host = p.host else { return false }
        let purchase = (host == "buy.itunes.apple.com" || host.range(of:"^p[0-9]+-buy[.]itunes[.]apple[.]com$", options:.regularExpression) != nil)
            && p.percentEncodedPath == "/WebObjects/MZFinance.woa/wa/buyProduct"
        return purchase || (host == "downloaddispatch.itunes.apple.com" && p.percentEncodedPath == "/WebObjects/DownloadDispatch.woa/wa/ent/download")
    }

    static func commerceHeaders(for endpoint: URL) throws -> [(String, String)] {
        guard commerceApproved(endpoint) else { throw NSError(domain:"StoreAMD", code:4) }
        return try proofHeaders(endpoint, required: true)
    }

    private static func proofHeaders(_ endpoint: URL, required: Bool) throws -> [(String, String)] {
        let bag = try bag()
        return try autoreleasepool {
            let selector = NSSelectorFromString("headersForRequest:account:type:bag:")
            guard let cls = NSClassFromString("AMSAnisette"), let method = class_getClassMethod(cls, selector) else { throw NSError(domain:"StoreAMD", code:2) }
            typealias Headers = @convention(c) (AnyObject, Selector, AnyObject, AnyObject?, Int64, AnyObject) -> Unmanaged<AnyObject>?
            let call = unsafeBitCast(method_getImplementation(method), to: Headers.self)
            guard let pending = call(cls as AnyObject, selector, NSURLRequest(url:endpoint), nil, 2, bag)?.takeUnretainedValue(),
                  let values = resolved(pending) as? [String:Any] else { throw NSError(domain:"StoreAMD", code:3) }
            if values.isEmpty && !required { return [] }
            return try validated(values)
        }
    }

    static func handle(_ response: HTTPURLResponse) throws -> Bool {
        guard let url = response.url else { return false }
        _ = try Authenticator.approvedEndpoint(url)
        guard url.host == "auth.itunes.apple.com", response.value(forHTTPHeaderField:"X-Apple-AMD-Action") == "SP" else { return false }
        let bag = try bag()
        guard let cls = NSClassFromString("AMSAnisette"), let actionClass = NSClassFromString("AMSURLAction") else { return false }
        let selector = NSSelectorFromString("handleResponse:type:bag:account:")
        guard let method = class_getClassMethod(cls, selector) else { return false }
        typealias Handle = @convention(c) (AnyObject, Selector, AnyObject, Int64, AnyObject, AnyObject?) -> Unmanaged<AnyObject>?
        let call = unsafeBitCast(method_getImplementation(method), to: Handle.self)
        guard let pending = call(cls as AnyObject, selector, response, 2, bag, nil)?.takeUnretainedValue(),
              let result = resolved(pending) as? NSObject, result.isKind(of:actionClass) else { return false }
        return retryAction(result)
    }

    static func retryAction(_ result: NSObject) -> Bool {
        let errorSelector = NSSelectorFromString("error"), typeSelector = NSSelectorFromString("actionType")
        guard result.responds(to:errorSelector), result.responds(to:typeSelector),
              let errorMethod = class_getInstanceMethod(object_getClass(result),errorSelector),
              let typeMethod = class_getInstanceMethod(object_getClass(result),typeSelector),
              let cls = NSClassFromString("AMSURLAction"), let retryMethod = class_getClassMethod(cls,NSSelectorFromString("retryAction")) else { return false }
        typealias Object = @convention(c) (AnyObject, Selector) -> Unmanaged<AnyObject>?
        typealias Number = @convention(c) (AnyObject, Selector) -> Int64
        let error = unsafeBitCast(method_getImplementation(errorMethod), to:Object.self)
        guard error(result,errorSelector) == nil else { return false }
        let expectedCall = unsafeBitCast(method_getImplementation(retryMethod), to:Object.self)
        guard let expected = expectedCall(cls as AnyObject,NSSelectorFromString("retryAction"))?.takeUnretainedValue(),
              let expectedMethod = class_getInstanceMethod(object_getClass(expected),typeSelector) else { return false }
        return unsafeBitCast(method_getImplementation(typeMethod), to:Number.self)(result,typeSelector)
            == unsafeBitCast(method_getImplementation(expectedMethod), to:Number.self)(expected,typeSelector)
    }

    static func validated(_ values: [String:Any]) throws -> [(String,String)] {
        try ["X-Apple-AMD","X-Apple-AMD-M"].map { key in
            guard let value = values[key] as? String, !value.isEmpty, value.utf8.count <= 8192,
                  !value.unicodeScalars.contains(where: { $0.value == 13 || $0.value == 10 }) else { throw NSError(domain:"StoreAMD",code:4) }
            return (key,value)
        }
    }
}
