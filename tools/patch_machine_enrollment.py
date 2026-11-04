"""Patch the pinned login command to hand off only the needed private session."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
auth = root / "Sources/ApplePackage/Commands/Authenticate.swift"
source = auth.read_text()
if source.count("return .codeRequired") != 1:
    raise SystemExit("pinned authentication parser changed")
source = source.replace("return .codeRequired", 'return .failure("apple_auth_ambiguous_bad_login")')
changes = [
    ('    private var storeFront = ""', '    private var storeFront = ""\n    private var labStoreFront: String?'),
    ('        let readStoreFrontValue = response.headers["x-set-apple-store-front"]',
     '        labStoreFront = response.headers.first(name: "x-set-apple-store-front") ?? labStoreFront\n        let readStoreFrontValue = response.headers["x-set-apple-store-front"]'),
    ("        let account = try Account(", "        var account = try Account("),
    ("        return .success(account)", "        account.labStoreFront = labStoreFront\n        return .success(account)"),
    ("        cookies.mergeCookies(response.cookies)", """        var scopedCookies = Dictionary(cookies.map { ($0.name, $0) }, uniquingKeysWith: { _, last in last })
        for rawCookie in response.cookies {
            var scoped = Cookie(copyFrom: rawCookie)
            if scoped.domain == nil { scoped.domain = endpoint.host }
            scopedCookies[scoped.name] = scoped
        }
        cookies = Array(scopedCookies.values)"""),
]
for before, after in changes:
    if source.count(before) != 1:
        raise SystemExit("pinned private session source changed")
    source = source.replace(before, after)
purpose_changes = [
    ("                sapSigner: signer,", """                sapSigner: signer,
                machineAuthorization: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "machineAuthorize","""),
    ("        sapSigner: any SAPRequestSigning,", "        sapSigner: any SAPRequestSigning, machineAuthorization: Bool = false,"),
    ('"rmp": "0", "why": "signIn",', '"rmp": "0", "why": machineAuthorization ? "machineAuthorize" : "signIn",'),
]
for before, after in purpose_changes:
    if source.count(before) != 1:
        raise SystemExit("pinned authentication purpose source changed")
    source = source.replace(before, after)
session_changes = [
    ('                machineAuthorization: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "machineAuthorize",',
     """                machineAuthorization: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "machineAuthorize",
                createMachineSession: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "machineSession","""),
    ("machineAuthorization: Bool = false,", "machineAuthorization: Bool = false, createMachineSession: Bool = false,"),
    ("        let parameters: [String: String] = [", "        var parameters: [String: String] = ["),
    ('"why": machineAuthorization ? "machineAuthorize" : "signIn",',
     '"why": (machineAuthorization || createMachineSession) ? "machineAuthorize" : "signIn",'),
    ("        let data = try PropertyListSerialization.data(fromPropertyList: parameters, format: .xml, options: 0)",
     """        if createMachineSession {
            parameters.removeValue(forKey: "rmp")
            parameters["attempt"] = "1"
            parameters["createSession"] = "true"
            parameters["machineName"] = ProcessInfo.processInfo.hostName
        }
        let data = try PropertyListSerialization.data(fromPropertyList: parameters, format: .xml, options: 0)"""),
]
for before, after in session_changes:
    if source.count(before) != 1:
        raise SystemExit("pinned machine session source changed")
    source = source.replace(before, after)
auth.write_text(source)

tests = root / "Tests/ApplePackageTests/SAPAuthenticationRequestTests.swift"
source_tests = tests.read_text()
before = "    func testSignatureCoversExactSerializedHTTPBody() async throws {"
after = """    func testMachineAuthorizationPurposeIsSignedIntoTheExactBody() async throws {
        let signer = RecordingSigner()
        let request = try await Authenticator.makeRequest(
            endpoint: XCTUnwrap(URL(string: "https://auth.itunes.apple.com/login")),
            email: "reader@example.invalid", password: "synthetic-password", code: "",
            cookies: [], deviceIdentifier: "001122334455", sapSigner: signer, machineAuthorization: true,
        )
        let body = try bodyData(request)
        let signedBodies = await signer.recordedBodies()
        XCTAssertEqual(signedBodies, [body])
        let parameters = try XCTUnwrap(PropertyListSerialization.propertyList(from: body, format: nil) as? [String: String])
        XCTAssertEqual(parameters["why"], "machineAuthorize")
        XCTAssertEqual(parameters["password"], "synthetic-password")
        XCTAssertEqual(parameters["guid"], "001122334455")
    }

""" + before
if source_tests.count(before) != 1:
    raise SystemExit("pinned authentication purpose test changed")
tests.write_text(source_tests.replace(before, after))

account = root / "Sources/ApplePackage/Models/Account.swift"
source = account.read_text()
before = "    public var pod: String?"
if source.count(before) != 1:
    raise SystemExit("pinned account model changed")
account.write_text(source.replace(before, "    public var labStoreFront: String?\n" + before))

login = root / "Sources/ApplePackageTool/Commands/Login.swift"
source = login.read_text()
before = "                Configuration.saveLoginAccount(account, for: email)"
after = """                if let destination = ProcessInfo.processInfo.environment["LAB_ENROLLMENT_INPUT_PATH"] {
                    guard ProcessInfo.processInfo.environment["GITHUB_ACTIONS"] == "true" else {
                        throw ValidationError("GitHub-hosted trial required")
                    }
                    let cookieData = try JSONEncoder().encode(account.cookie)
                    let payload: [String: Any] = [
                        "dsid": account.directoryServicesIdentifier,
                        "token": account.passwordToken,
                        "guid": Configuration.deviceIdentifier,
                        "storefront": account.labStoreFront ?? "\\(account.store)-1",
                        "cookies": try JSONSerialization.jsonObject(with: cookieData),
                    ]
                    let data = try JSONSerialization.data(withJSONObject: payload)
                    guard FileManager.default.createFile(atPath: destination, contents: data,
                        attributes: [.posixPermissions: 0o600]) else {
                        throw ValidationError("Private session handoff failed")
                    }
                    return
                }
                Configuration.saveLoginAccount(account, for: email)"""
if source.count(before) != 1:
    raise SystemExit("pinned login handoff changed")
login.write_text(source.replace(before, after))

source_tests = tests.read_text()
before = "    func testMachineAuthorizationPurposeIsSignedIntoTheExactBody() async throws {"
after = """    func testMachineSessionFieldsAreSignedIntoTheExactBody() async throws {
        let signer = RecordingSigner()
        let request = try await Authenticator.makeRequest(
            endpoint: XCTUnwrap(URL(string: "https://auth.itunes.apple.com/login")),
            email: "reader@example.invalid", password: "synthetic-password", code: "",
            cookies: [], deviceIdentifier: "001122334455", sapSigner: signer, createMachineSession: true,
        )
        let body = try bodyData(request)
        let signedBodies = await signer.recordedBodies()
        XCTAssertEqual(signedBodies, [body])
        let parameters = try XCTUnwrap(PropertyListSerialization.propertyList(from: body, format: nil) as? [String: String])
        XCTAssertEqual(parameters["why"], "machineAuthorize")
        XCTAssertEqual(parameters["createSession"], "true")
        XCTAssertEqual(parameters["attempt"], "1")
        XCTAssertEqual(parameters["machineName"], ProcessInfo.processInfo.hostName)
        XCTAssertEqual(parameters["guid"], "001122334455")
        XCTAssertNil(parameters["rmp"])
    }

""" + before
if source_tests.count(before) != 1:
    raise SystemExit("pinned machine session test changed")
tests.write_text(source_tests.replace(before, after))

# Preserve the native plist boolean type rather than the legacy string "true".
source = auth.read_text()
boolean_changes = [
    ('                createMachineSession: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "machineSession",',
     '''                createMachineSession: ["machineSession", "booleanSession"].contains(ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] ?? ""),
                booleanMachineSession: ProcessInfo.processInfo.environment["LAB_AUTHORIZATION_PURPOSE"] == "booleanSession",'''),
    ("createMachineSession: Bool = false,", "createMachineSession: Bool = false, booleanMachineSession: Bool = false,"),
    ("        var parameters: [String: String] = [", "        var parameters: [String: Any] = ["),
    ('            parameters["createSession"] = "true"', '            parameters["createSession"] = booleanMachineSession ? (true as Any) : ("true" as Any)'),
]
for before, after in boolean_changes:
    if source.count(before) != 1:
        raise SystemExit("pinned boolean session source changed")
    source = source.replace(before, after)
auth.write_text(source)

source_tests = tests.read_text()
before = "    func testMachineSessionFieldsAreSignedIntoTheExactBody() async throws {"
after = """    func testBooleanMachineSessionPreservesNativePlistTypeAndSignature() async throws {
        let signer = RecordingSigner()
        let request = try await Authenticator.makeRequest(
            endpoint: XCTUnwrap(URL(string: "https://auth.itunes.apple.com/login")),
            email: "reader@example.invalid", password: "synthetic-password", code: "",
            cookies: [], deviceIdentifier: "001122334455", sapSigner: signer,
            createMachineSession: true, booleanMachineSession: true,
        )
        let body = try bodyData(request)
        let signedBodies = await signer.recordedBodies()
        XCTAssertEqual(signedBodies, [body])
        let parameters = try XCTUnwrap(PropertyListSerialization.propertyList(from: body, format: nil) as? [String: Any])
        XCTAssertEqual(parameters["createSession"] as? Bool, true)
        XCTAssertNil(parameters["createSession"] as? String)
        XCTAssertTrue(String(decoding: body, as: UTF8.self).contains("<true/>"))
        XCTAssertEqual(parameters["why"] as? String, "machineAuthorize")
        XCTAssertEqual(parameters["attempt"] as? String, "1")
        XCTAssertEqual(parameters["guid"] as? String, "001122334455")
        XCTAssertNil(parameters["rmp"])
    }

""" + before
if source_tests.count(before) != 1:
    raise SystemExit("pinned boolean session test changed")
tests.write_text(source_tests.replace(before, after))

# Observe fixed challenge flags across login responses without publishing values.
source = auth.read_text()
challenge_changes = [
    ('    private var labStoreFront: String?',
     '    private var labStoreFront: String?\n    private var labProvisioningSummary: [String: Bool] = [:]'),
    ('        labStoreFront = response.headers.first(name: "x-set-apple-store-front") ?? labStoreFront',
     '''        for (key, present) in Self.provisioningChallengeSummary(response.headers) {
            labProvisioningSummary[key] = (labProvisioningSummary[key] ?? false) || present
        }
        labStoreFront = response.headers.first(name: "x-set-apple-store-front") ?? labStoreFront'''),
    ('        account.labStoreFront = labStoreFront',
     '        account.labStoreFront = labStoreFront\n        account.labProvisioningSummary = labProvisioningSummary'),
    ('    static func approvedEndpoint(_ url: URL) throws -> URL {', r'''    static func provisioningChallengeSummary(_ headers: HTTPHeaders) -> [String: Bool] {
        var result: [String: Bool] = [:]
        for scope in ["md", "amd"] {
            let action = headers.first(name: "x-apple-\(scope)-action") ?? ""
            let encoded = headers.first(name: "x-apple-\(scope)-data") ?? ""
            let prefix = "login_\(scope)_"
            result[prefix + "action_present"] = !action.isEmpty
            result[prefix + "provision_requested"] = action == "SP"
            result[prefix + "sync_requested"] = action == "SM"
            result[prefix + "reset_requested"] = action == "RP"
            result[prefix + "data_present"] = !encoded.isEmpty
            result[prefix + "data_valid"] = !encoded.isEmpty && encoded.utf8.count <= 1048576
                && !(Data(base64Encoded: encoded)?.isEmpty ?? true)
        }
        return result
    }

    static func approvedEndpoint(_ url: URL) throws -> URL {'''),
]
for before, after in challenge_changes:
    if source.count(before) != 1:
        raise SystemExit("pinned login challenge source changed")
    source = source.replace(before, after)
auth.write_text(source)

source = account.read_text()
before = "    public var labStoreFront: String?"
if source.count(before) != 1:
    raise SystemExit("pinned login challenge account changed")
account.write_text(source.replace(before, before + "\n    public var labProvisioningSummary: [String: Bool] = [:]"))
source = login.read_text()
before = '                        "token": account.passwordToken,'
if source.count(before) != 1:
    raise SystemExit("pinned login challenge handoff changed")
login.write_text(source.replace(before, before + '\n                        "login_provisioning": account.labProvisioningSummary,'))

source_tests = tests.read_text()
source_tests = source_tests.replace("import NIOCore\n", "import NIOCore\nimport NIOHTTP1\n")
before = "    func testBooleanMachineSessionPreservesNativePlistTypeAndSignature() async throws {"
after = '''    func testProvisioningSummaryClassifiesBothScopesWithoutLeakingHeaders() throws {
        let empty = Authenticator.provisioningChallengeSummary(HTTPHeaders())
        XCTAssertEqual(empty.count, 12)
        XCTAssertTrue(empty.values.allSatisfy { !$0 })
        let headers = HTTPHeaders([
            ("x-APPLE-MD-Action", "SP"), ("X-Apple-MD-Data", "U1lOVEhFVElD"),
            ("X-Apple-AMD-Action", "SM"), ("x-apple-amd-data", "U1lOVEhFVElD"),
            ("Set-Cookie", "PRIVATE_SYNTHETIC"),
        ])
        let summary = Authenticator.provisioningChallengeSummary(headers)
        XCTAssertEqual(summary["login_md_provision_requested"], true)
        XCTAssertEqual(summary["login_amd_sync_requested"], true)
        XCTAssertEqual(summary["login_md_data_valid"], true)
        XCTAssertEqual(summary["login_amd_data_valid"], true)
        XCTAssertEqual(summary["login_amd_reset_requested"], false)
        let bad = Authenticator.provisioningChallengeSummary(HTTPHeaders([
            ("X-Apple-MD-Action", "PRIVATE_SYNTHETIC"), ("X-Apple-MD-Data", "not base64!"),
            ("X-Apple-AMD-Action", "RP"),
        ]))
        XCTAssertEqual(bad["login_md_action_present"], true)
        XCTAssertEqual(bad["login_md_provision_requested"], false)
        XCTAssertEqual(bad["login_md_data_present"], true)
        XCTAssertEqual(bad["login_md_data_valid"], false)
        XCTAssertEqual(bad["login_amd_reset_requested"], true)
        let publicJSON = String(decoding: try JSONEncoder().encode([empty, summary, bad]), as: UTF8.self)
        XCTAssertFalse(publicJSON.contains("PRIVATE_SYNTHETIC"))
        XCTAssertFalse(publicJSON.contains("U1lOVEhFVElD"))
    }

''' + before
if source_tests.count(before) != 1:
    raise SystemExit("pinned login challenge test changed")
tests.write_text(source_tests.replace(before, after))

# Hand off the actual login User-Agent for an explicit same-client control.
source = login.read_text()
before = '                        "guid": Configuration.deviceIdentifier,'
if source.count(before) != 1:
    raise SystemExit("pinned login client metadata handoff changed")
login.write_text(source.replace(before, before + '\n                        "user_agent": Configuration.userAgent,'))
