"""Capture bounded account-free framework metadata; discard native stderr."""
import json
import os
import subprocess

def main():
    result = {"status": "capability_probe_failed", "account_login_attempted": False,
              "enrollment_created": False, "decryption_proven": False}
    if os.environ.get("GITHUB_ACTIONS") != "true":
        result["status"] = "requires_github_actions"
    else:
        try:
            run = subprocess.run(["./authkit-capabilities"], capture_output=True, text=True, timeout=20,
                                 stdin=subprocess.DEVNULL,
                                 env={"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"})
            if run.returncode == 0 and len(run.stdout) <= 32768:
                raw = json.loads(run.stdout)
                if raw.get("schema") == "ipa-lab-authkit-capabilities-v1":
                    result = raw
                    result["status"] = "capabilities_observed"
        except Exception:
            pass
    result.update(account_login_attempted=False, enrollment_created=False, decryption_proven=False)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "capabilities_observed" else 2

if __name__ == "__main__":
    raise SystemExit(main())
