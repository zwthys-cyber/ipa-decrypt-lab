"""Patch only the separately built CN authentication variant."""
from pathlib import Path
import shutil
import sys
root=Path(sys.argv[1]);ops=Path(__file__).resolve().parent
path=root/'Sources/ApplePackageTool/ApplePackageTool.swift'
s=path.read_text();old='subcommands: [Login.self, Logout.self, Search.self, Versions.self, Download.self]'
assert s.count(old)==1
path.write_text(s.replace(old,old[:-1]+', ChinaLogin.self, ChinaResume.self]'))
for name,target in [('ChinaLogin.swift','Sources/ApplePackageTool/Commands/ChinaLogin.swift'),
                    ('LabCNLoginFlow.swift','Sources/ApplePackage/Commands/LabCNLoginFlow.swift'),
                    ('LabCNLoginFlowTests.swift','Tests/ApplePackageTests/LabCNLoginFlowTests.swift')]:
    shutil.copyfile(ops/name,root/target)
