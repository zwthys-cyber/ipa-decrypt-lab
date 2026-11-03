"""Apply the pinned ent/download compatibility layer in GitHub Actions only."""
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1])
def replace(path, before, after):
    target = root/path
    source = target.read_text()
    if source.count(before) != 1:
        raise SystemExit("pinned ent/download source changed: " + path)
    target.write_text(source.replace(before, after))

replace("Sources/ApplePackage/Models/Account.swift",
        "    public var pod: String?",
        "    public var labStoreFront: String?\n    public var pod: String?")
replace("Sources/ApplePackage/Commands/Authenticate.swift",
        '    private var storeFront = ""',
        '    private var storeFront = ""\n    private var labStoreFront: String?')
replace("Sources/ApplePackage/Commands/Authenticate.swift",
        '        let readStoreFrontValue = response.headers["x-set-apple-store-front"]',
        '        if let full = response.headers.first(name: "x-set-apple-store-front"), !full.isEmpty {\n            labStoreFront = full\n        }\n        let readStoreFrontValue = response.headers["x-set-apple-store-front"]')
replace("Sources/ApplePackage/Commands/Authenticate.swift",
        "        let account = try Account(", "        var account = try Account(")
replace("Sources/ApplePackage/Commands/Authenticate.swift",
        "        return .success(account)",
        "        account.labStoreFront = labStoreFront\n        return .success(account)")
replace("Sources/ApplePackage/Commands/Purchase.swift",
        '("X-Apple-Store-Front", "\\(account.store)-1"),',
        '("X-Apple-Store-Front", account.labStoreFront ?? "\\(account.store)-1"),')
replace("Sources/ApplePackage/Commands/Purchase.swift",
        '            switch failureType {',
        '            switch failureType {\n            case "5002":\n                throw NSError(domain: "LabPurchaseUnconfirmed", code: 5002)')
replace("Sources/ApplePackageTool/Commands/Download.swift",
        "            try await Purchase.purchase(account: &account, app: app)",
        """            do {
                try await Purchase.purchase(account: &account, app: app)
            } catch let error as NSError where error.domain == "LabPurchaseUnconfirmed" && error.code == 5002 {
                // Not proof of entitlement: let the authenticated download response decide.
                print("IPA_LAB_LICENSE:unconfirmed_5002")
            }""")
replace("Sources/ApplePackage/Commands/Bag.swift",
        "        public var updateEndpoint: URL?",
        "        public var updateEndpoint: URL?\n        public var entDownloadEndpoint: URL?")
replace("Sources/ApplePackage/Commands/Bag.swift",
        '            updateEndpoint: downloadEndpoint(plist["updateProduct"] ?? urlBag["updateProduct"], path: "/up/updateProduct"),',
        '            updateEndpoint: downloadEndpoint(plist["updateProduct"] ?? urlBag["updateProduct"], path: "/up/updateProduct"),\n            entDownloadEndpoint: downloadEndpoint(plist["volumeStoreDownloadProduct"] ?? urlBag["volumeStoreDownloadProduct"], path: LabEntDownload.endpointPath),')
replace("Sources/ApplePackage/Commands/StoreDownloadEndpoint+Fetch.swift",
        "        let dict = try await StoreDownloadEndpoint.volumeStore.fetchProduct(",
        """        if let helper = ProcessInfo.processInfo.environment["LAB_KBSYNC_HELPER"], !helper.isEmpty {
            return try await LabEntDownload.fetch(client: client, account: &account, app: app,
                guid: deviceIdentifier, version: externalVersionID, helper: helper)
        }
        let dict = try await StoreDownloadEndpoint.volumeStore.fetchProduct(""")
shutil.copyfile("tools/LabEntDownload.swift", root/"Sources/ApplePackage/Commands/LabEntDownload.swift")
shutil.copyfile("tests/LabEntDownloadTests.swift", root/"Tests/ApplePackageTests/LabEntDownloadTests.swift")
