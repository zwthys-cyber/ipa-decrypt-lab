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
after = '''            let downloadOutput: DownloadOutput
            do {
                downloadOutput = try await ApplePackage.Download.download(
                    account: &account, app: app, externalVersionID: resolvedVersionID
                )
            } catch ApplePackageError.licenseRequired {
                guard let price = app.price, price == 0 else {
                    throw ApplePackageError.licenseRequired
                }
                try await Purchase.purchase(account: &account, app: app)
                downloadOutput = try await ApplePackage.Download.download(
                    account: &account, app: app, externalVersionID: resolvedVersionID
                )
            }'''
if source.count(before) != 1:
    raise SystemExit("pinned download operation changed; refusing patch")
download.write_text(source.replace(before, after))
