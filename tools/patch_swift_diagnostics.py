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
