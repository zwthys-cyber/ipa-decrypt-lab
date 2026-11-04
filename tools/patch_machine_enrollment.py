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
auth.write_text(source)
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
