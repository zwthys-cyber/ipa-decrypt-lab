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
