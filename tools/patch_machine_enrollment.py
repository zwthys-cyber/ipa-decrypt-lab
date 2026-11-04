"""Patch the pinned login command to hand off only the needed private session."""
from pathlib import Path
import sys

root = Path(sys.argv[1])
auth = root / "Sources/ApplePackage/Commands/Authenticate.swift"
source = auth.read_text()
if source.count("return .codeRequired") != 1:
    raise SystemExit("pinned authentication parser changed")
auth.write_text(source.replace("return .codeRequired", 'return .failure("apple_auth_ambiguous_bad_login")'))

login = root / "Sources/ApplePackageTool/Commands/Login.swift"
source = login.read_text()
before = "                Configuration.saveLoginAccount(account, for: email)"
after = """                if let destination = ProcessInfo.processInfo.environment["LAB_ENROLLMENT_INPUT_PATH"] {
                    guard ProcessInfo.processInfo.environment["GITHUB_ACTIONS"] == "true" else {
                        throw ValidationError("GitHub-hosted trial required")
                    }
                    let payload: [String: String] = [
                        "dsid": account.directoryServicesIdentifier,
                        "token": account.passwordToken,
                        "guid": Configuration.deviceIdentifier,
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
