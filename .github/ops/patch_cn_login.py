"""Patch only the separately built CN authentication variant."""
from pathlib import Path
import shutil
import sys
root=Path(sys.argv[1]);ops=Path(__file__).resolve().parent
path=root/'Sources/ApplePackageTool/ApplePackageTool.swift'
s=path.read_text();old='subcommands: [Login.self, Logout.self, Search.self, Versions.self, Download.self]'
assert s.count(old)==1
path.write_text(s.replace(old,old[:-1]+', ChinaLogin.self, ChinaResume.self, ChinaSummary.self]'))
for name,target in [('ChinaLogin.swift','Sources/ApplePackageTool/Commands/ChinaLogin.swift'),
                    ('LabCNLoginFlow.swift','Sources/ApplePackage/Commands/LabCNLoginFlow.swift'),
                    ('LabCNLoginFlowTests.swift','Tests/ApplePackageTests/LabCNLoginFlowTests.swift')]:
    shutil.copyfile(ops/name,root/target)

for name,target in [('LabCNSummary.swift','Sources/ApplePackage/Commands/LabCNSummary.swift'),
                    ('LabCNSummaryTests.swift','Tests/ApplePackageTests/LabCNSummaryTests.swift')]:
    shutil.copyfile(ops/name,root/target)
proof=root/'Sources/ApplePackage/Commands/StoreAMD.swift'
value=proof.read_text();anchor='    static func commerceHeaders(for endpoint: URL) throws -> [(String, String)] {'
assert value.count(anchor)==1
addition='    static func cnSummaryHeaders(for endpoint: URL) throws -> [(String, String)] {\n        guard LabCNSummary.approved(endpoint) else { throw NSError(domain:"CNSummaryInput",code:3) }\n        return try proofHeaders(endpoint, required:true)\n    }\n\n'
proof.write_text(value.replace(anchor,addition+anchor))
