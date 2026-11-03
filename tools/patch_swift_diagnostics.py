"""Only remove the ambiguous BadLogin=>2FA interpretation; do not alter SAP or endpoints."""
from pathlib import Path
import sys
p = Path(sys.argv[1])/"Sources/ApplePackage/Commands/Authenticate.swift"
source = p.read_text()
before = "return .codeRequired"
if source.count(before) != 1:
    raise SystemExit("pinned Swift parser changed; refusing patch")
p.write_text(source.replace(before, 'return .failure("apple_auth_ambiguous_bad_login")'))
