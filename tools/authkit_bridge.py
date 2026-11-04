"""Run the native synthetic callback contract privately on GitHub."""
import json
import os
import subprocess

def main():
    result = {"schema": "ipa-lab-authkit-bridge-v1", "status": "bridge_probe_failed"}
    if os.environ.get("GITHUB_ACTIONS") != "true":
        result["status"] = "requires_github_actions"
    else:
        try:
            run = subprocess.run(["./authkit-bridge", "--self-test"], capture_output=True, text=True,
                stdin=subprocess.DEVNULL, timeout=20,
                env={"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"})
            if len(run.stdout) <= 8192:
                raw = json.loads(run.stdout)
                if raw.get("schema") == "ipa-lab-authkit-bridge-v1":
                    result = raw
                    if run.returncode != 0 and result.get("status") == "contract_verified":
                        result["status"] = "bridge_probe_failed"
        except Exception:
            pass
    result.update(account_login_attempted=False, native_account_created=False,
                  enrollment_created=False, decryption_proven=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "contract_verified" else 2

if __name__ == "__main__":
    raise SystemExit(main())
