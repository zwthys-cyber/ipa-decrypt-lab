"""Instrument only a CI-built diagnostic client; no request changes."""
from pathlib import Path
import sys
import os
root=Path(sys.argv[1]);ops=Path(__file__).resolve().parent
path=root/"Sources/ApplePackage/Commands/Purchase.swift"
source=path.read_text()
def replace(before,after):
    global source
    assert source.count(before)==1,"pinned_purchase_source_changed"
    source=source.replace(before,after)
replace("        let request = try makeRequest(", '        print("IPA_CN_PURCHASE_PHASE:prepare_request")\n        let request = try makeRequest(')
replace("        let response = try await client.execute(request: request).get()", '        print("IPA_CN_PURCHASE_PHASE:send_request")\n        let response = try await client.execute(request: request).get()\n        print("IPA_CN_PURCHASE_HTTP:" + String(response.status.code))')
replace("        let plist = try PropertyListSerialization.propertyList(", '        print("IPA_CN_PURCHASE_PHASE:parse_response")\n        let plist = try PropertyListSerialization.propertyList(')
replace("        guard let dict = plist else { try ensureFailed(Strings.invalidResponse) }",'        guard let dict = plist else {\n            print("IPA_CN_PURCHASE_ROOT:not_dictionary")\n            try ensureFailed(Strings.invalidResponse)\n        }\n        for line in LabCNPurchaseTrace.lines(dict) { print(line) }')
path.write_text(source)
(root/"Sources/ApplePackage/Commands/LabCNPurchaseTrace.swift").write_text((ops/"LabCNPurchaseTrace.swift").read_text())
(root/"Tests/ApplePackageTests/LabCNPurchaseTraceTests.swift").write_text((ops/"LabCNPurchaseTraceTests.swift").read_text())

if os.environ.get("CN_LICENSE_CONTROL")=="existing_entitlement":
    path=root/"Sources/ApplePackageTool/Commands/Download.swift"
    source=path.read_text()
    begin=source.index('            print("IPA_LAB_STAGE:acquire_free_license")')
    end=source.index('            if ProcessInfo.processInfo.environment["LAB_VERSION_CATALOG"]',begin)
    block=source[begin:end]
    assert block.count("try await Purchase.purchase(account: &account, app: app)")==1
    assert "LabPurchaseUnconfirmed" in block
    source=source[:begin]+'            print("IPA_CN_LICENSE_CONTROL:existing_entitlement")\n'+source[end:]
    path.write_text(source)
