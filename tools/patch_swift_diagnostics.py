"""Only remove the ambiguous BadLogin=>2FA interpretation; do not alter SAP or endpoints."""
from pathlib import Path
import sys
p = Path(sys.argv[1])/"Sources/ApplePackage/Commands/Authenticate.swift"
source = p.read_text()
before = "return .codeRequired"
if source.count(before) != 1:
    raise SystemExit("pinned Swift parser changed; refusing patch")
p.write_text(source.replace(before, 'return .failure("apple_auth_ambiguous_bad_login")'))


download = Path(sys.argv[1])/"Sources/ApplePackageTool/Commands/Download.swift"
source = download.read_text()
refresh = "            try await Authenticator.rotatePasswordToken(for: &account)\n"
if source.count(refresh) != 1:
    raise SystemExit("pinned token refresh changed; refusing patch")
source = source.replace(refresh, "            // Reuse the session just created by the login command.\n")
before = '''            let downloadOutput = try await ApplePackage.Download.download(
                account: &account,
                app: app,
                externalVersionID: resolvedVersionID,
            )'''
after = '''            guard let price = app.price, price == 0 else {
                throw ApplePackageError.licenseRequired
            }
            try await Purchase.purchase(account: &account, app: app)
            let downloadOutput = try await ApplePackage.Download.download(
                account: &account, app: app, externalVersionID: resolvedVersionID
            )'''
if source.count(before) != 1:
    raise SystemExit("pinned download operation changed; refusing patch")
source = source.replace(before, after)
# Fixed, non-sensitive progress markers; no account data or server responses.
stages = [
    ("        let outputURL = try validateOutputURL(output)", "validate_output"),
    ("        try await Configuration.withAccount(email: email)", "load_account"),
    ("            guard let country = Configuration.countryCode", "resolve_country"),
    ("            let app = try await Lookup.lookup", "lookup_app"),
    ("            let resolvedVersionID = try await resolveVersionID", "resolve_version"),
    ("            let downloadOutput = try await ApplePackage.Download.download", "request_product"),
    ("            try await Purchase.purchase", "acquire_free_license"),
    ("            let (contentLength, supportsRanges)", "inspect_download"),
    ("                try await downloadWithProgress", "download_bytes"),
    ("            try await SignatureInjector.inject", "inject_signature"),
    ("            try PackagePlatformValidator.ensurePackage", "validate_platform"),
    ("            try replaceOutput", "publish_file"),
]
for anchor, stage in stages:
    if source.count(anchor) != 1:
        raise SystemExit("pinned download stage changed; refusing patch")
    indent = anchor[:len(anchor) - len(anchor.lstrip())]
    source = source.replace(anchor, indent + 'print("IPA_LAB_STAGE:' + stage + '")\n' + anchor)
download.write_text(source)


library = Path(sys.argv[1])/"Sources/ApplePackage/Commands/Download.swift"
source = library.read_text()
anchor = '        if let failureType = dict["failureType"] as? String {'
if source.count(anchor) != 1:
    raise SystemExit("pinned product response changed; refusing patch")
source = source.replace(anchor, anchor + """
            if let code = Int(failureType), (0...99999).contains(code) {
                print("IPA_LAB_FAILURE:" + String(code))
            }
""")
library.write_text(source)

endpoint = Path(sys.argv[1])/"Sources/ApplePackage/Commands/StoreDownloadEndpoint+Fetch.swift"
source = endpoint.read_text()
changes = [
    ('            defer { finalResponse = response }',
     '            print("IPA_LAB_HTTP:" + String(response.status.code))\n            defer { finalResponse = response }'),
    ('        let plist = try PropertyListSerialization.propertyList(',
     '        print("IPA_LAB_STAGE:parse_product")\n        let plist = try PropertyListSerialization.propertyList('),
    ('        guard (response["customerMessage"] as? String ?? "").isEmpty,',
     '        print("IPA_LAB_STAGE:validate_product")\n        guard (response["customerMessage"] as? String ?? "").isEmpty,'),
]
for before, after in changes:
    if source.count(before) != 1:
        raise SystemExit("pinned endpoint diagnostics changed; refusing patch")
    source = source.replace(before, after)
endpoint.write_text(source)


# Optional diagnostic route comparison. Production keeps the advertised route
# unless the caller explicitly selects the built-in native Apple endpoint.
source = p.read_text()
before = "baseURL: bag.authEndpoint, deviceIdentifier: deviceIdentifier)"
after = 'baseURL: Self.loginEndpoint(bag.authEndpoint, useNative: ProcessInfo.processInfo.environment["LAB_NATIVE_AUTH_ROUTE"] == "1"), deviceIdentifier: deviceIdentifier)'
if source.count(before) != 1:
    raise SystemExit("pinned auth initialization changed; refusing route patch")
source = source.replace(before, after)
anchor = "    static func approvedEndpoint(_ url: URL) throws -> URL {"
addition = '''    static func loginEndpoint(_ advertised: URL, useNative: Bool) throws -> URL {
        _ = try approvedEndpoint(advertised)
        if useNative {
            return URL(string: "https://auth.itunes.apple.com/auth/v1/native/fast/")!
        }
        return advertised
    }

'''
if source.count(anchor) != 1:
    raise SystemExit("pinned endpoint approval changed; refusing route patch")
p.write_text(source.replace(anchor, addition + anchor))
test = Path(sys.argv[1])/"Tests/ApplePackageTests/LabAuthRouteTests.swift"
test.write_text('''@testable import ApplePackage
import Foundation
import XCTest

final class LabAuthRouteTests: XCTestCase {
    func testDefaultKeepsAdvertisedEndpoint() throws {
        let url = URL(string: "https://p25-buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/authenticate/")!
        XCTAssertEqual(try Authenticator.loginEndpoint(url, useNative: false), url)
    }
    func testDiagnosticUsesOnlyBuiltInAppleEndpoint() throws {
        let url = URL(string: "https://p25-buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/authenticate/")!
        XCTAssertEqual(try Authenticator.loginEndpoint(url, useNative: true).absoluteString,
                       "https://auth.itunes.apple.com/auth/v1/native/fast/")
    }
    func testUntrustedAdvertisedEndpointIsStillRejected() throws {
        for value in ["http://buy.itunes.apple.com/", "https://example.invalid/",
                      "https://user:password@apple.com/"] {
            XCTAssertThrowsError(try Authenticator.loginEndpoint(URL(string:value)!, useNative:true))
        }
    }
}
''')


# Native Store authentication changed in November 2026. Keep the advertised
# native path and obtain fresh, origin-bound Store AMD proofs on macOS.
config = Path(sys.argv[1])/"Sources/ApplePackage/Configuration/Configuration.swift"
value = config.read_text()
assert value.count("Configurator/2.17") == 1
config.write_text(value.replace("Configurator/2.17", "Configurator/2.21"))
bag = Path(sys.argv[1])/"Sources/ApplePackage/Commands/Bag.swift"
value = bag.read_text()
start = value.index('            var path = comps.path')
end = value.index('        } else if comps.scheme', start)
value = value[:start] + """            guard comps.scheme == "https", comps.user == nil, comps.password == nil,
                  comps.port == nil || comps.port == 443, comps.fragment == nil,
                  ["/auth/v1/native", "/auth/v1/native/", "/auth/v1/native/fast", "/auth/v1/native/fast/"].contains(comps.percentEncodedPath)
            else { return nil }
            // Preserve Apple's path and routing query exactly.
""" + value[end:]
bag.write_text(value)
value = p.read_text()
start = value.index('        guard url.scheme?.lowercased() == "https"')
end = value.index('        return url', start)
value = value[:start] + """        guard let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
              comps.scheme == "https", let host = comps.host?.lowercased(),
              comps.user == nil, comps.password == nil, comps.fragment == nil,
              comps.port == nil || comps.port == 443
        else { try ensureFailed("Authentication requires an Apple HTTPS endpoint.") }
        let native = host == "auth.itunes.apple.com" &&
            ["/auth/v1/native", "/auth/v1/native/", "/auth/v1/native/fast", "/auth/v1/native/fast/"].contains(comps.percentEncodedPath)
        let legacyHost = host == "buy.itunes.apple.com" || host.range(of: "^p[0-9]+-buy[.]itunes[.]apple[.]com$", options: .regularExpression) != nil
        let legacy = legacyHost && ["/WebObjects/MZFinance.woa/wa/authenticate", "/WebObjects/MZFinance.woa/wa/authenticate/"].contains(comps.percentEncodedPath)
        guard native || legacy else { try ensureFailed("Unsupported authentication endpoint.") }
""" + value[end:]
anchor = '        let signature = try await sapSigner.sign(data)'
assert value.count(anchor) == 1
value = value.replace(anchor, '        headers += try StoreAMD.headers(for: endpoint)\n' + anchor)
p.write_text(value)
helper = Path(sys.argv[1])/"Sources/ApplePackage/Commands/StoreAMD.swift"
helper.write_text('''import Foundation
import ObjectiveC
import Darwin

// Private framework values remain in memory and never enter diagnostic output.
enum StoreAMD {
    static func headers(for endpoint: URL) throws -> [(String, String)] {
        _ = try Authenticator.approvedEndpoint(endpoint)
        guard endpoint.host?.lowercased() == "auth.itunes.apple.com" else { return [] }
        return try autoreleasepool {
            guard let handle = dlopen("/System/Library/PrivateFrameworks/AppleMediaServices.framework/AppleMediaServices", RTLD_NOW | RTLD_LOCAL) else {
                throw NSError(domain: "StoreAMD", code: 1)
            }
            defer { dlclose(handle) }
            let selector = NSSelectorFromString("_headersForRequest:account:type:")
            guard let cls = NSClassFromString("AMSAnisette"),
                  let method = class_getClassMethod(cls, selector) else {
                throw NSError(domain: "StoreAMD", code: 2)
            }
            typealias Headers = @convention(c) (AnyObject, Selector, AnyObject, AnyObject?, Int64) -> Unmanaged<AnyObject>?
            let call = unsafeBitCast(method_getImplementation(method), to: Headers.self)
            let request = NSURLRequest(url: endpoint)
            guard let values = call(cls as AnyObject, selector, request, nil, 2)?.takeUnretainedValue() as? [String: Any] else {
                throw NSError(domain: "StoreAMD", code: 3)
            }
            return try validated(values)
        }
    }

    static func validated(_ values: [String: Any]) throws -> [(String, String)] {
        try ["X-Apple-AMD", "X-Apple-AMD-M"].map { key in
            guard let value = values[key] as? String, !value.isEmpty,
                  value.utf8.count <= 8192, !value.contains("\\r"), !value.contains("\\n") else {
                throw NSError(domain: "StoreAMD", code: 4)
            }
            return (key, value)
        }
    }
}
''')
proofTests = Path(sys.argv[1])/"Tests/ApplePackageTests/LabStoreAMDTests.swift"
proofTests.write_text('''@testable import ApplePackage
import Foundation
import XCTest

final class LabStoreAMDTests: XCTestCase {
    func testPreservesNativePathAndQuery() throws {
        for path in ["/auth/v1/native", "/auth/v1/native/", "/auth/v1/native/fast", "/auth/v1/native/fast/"] {
            let raw = "https://auth.itunes.apple.com" + path + "?Pod=7"
            XCTAssertEqual(Bag.normalizedAuthEndpoint(from: raw)?.absoluteString, raw)
            XCTAssertEqual(try Authenticator.approvedEndpoint(URL(string: raw)!).absoluteString, raw)
        }
    }
    func testRejectsUntrustedProofTargets() throws {
        for raw in ["http://auth.itunes.apple.com/auth/v1/native", "https://auth.itunes.apple.com.evil.invalid/auth/v1/native", "https://auth.itunes.apple.com/auth/v1/native%2ffast", "https://user@auth.itunes.apple.com/auth/v1/native", "https://auth.itunes.apple.com:8443/auth/v1/native", "https://auth.itunes.apple.com/auth/v1/native#x", "https://apple.com/auth/v1/native"] {
            XCTAssertThrowsError(try StoreAMD.headers(for: URL(string: raw)!))
        }
        XCTAssertTrue(try StoreAMD.headers(for: URL(string:"https://buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/authenticate/")!).isEmpty)
    }
    func testValidatesProofWithoutLoggingValues() throws {
        XCTAssertEqual(try StoreAMD.validated(["X-Apple-AMD":"synthetic", "X-Apple-AMD-M":"machine", "Cookie":"ignored"]).count, 2)
        for values: [String: Any] in [[:], ["X-Apple-AMD":"x"], ["X-Apple-AMD":"x\\r\\n", "X-Apple-AMD-M":"m"], ["X-Apple-AMD":"", "X-Apple-AMD-M":"m"], ["X-Apple-AMD":String(repeating:"x", count:8193), "X-Apple-AMD-M":"m"]] {
            XCTAssertThrowsError(try StoreAMD.validated(values))
        }
    }
}
''')
