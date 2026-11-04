"""Classify rejection of a fixed invalid keybag; no login or server authorization."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from machine_enrollment import clean, native_command, stop_private_group

def run(user="runner"):
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean(None)
    binary = str(Path("native-machine-enrollment").resolve())
    with tempfile.TemporaryDirectory(prefix="ipa-lab-import-") as tmp:
        report = Path(tmp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true", "LAB_IMPORT_IO": "1", "HOME": os.environ.get("HOME", tmp)}
        child = subprocess.Popen(native_command(binary, report, env, user, probe=True), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            child.wait(timeout=45)
            if child.returncode or not report.is_file() or report.stat().st_size > 16384:
                return clean(None)
            return clean(json.loads(report.read_text()))
        except subprocess.TimeoutExpired:
            return clean({"status": "native_timeout"})
        finally:
            if child.poll() is None:
                stop_private_group(child, elevated=user == "root")
            child.wait(timeout=5)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-user", choices=("runner", "root"), default="runner")
    args = parser.parse_args()
    try:
        result = run(args.native_user)
    except Exception:
        result = clean(None)
    result["native_user"] = args.native_user
    if args.native_user == "root" and result.get("running_as_root") is not True:
        result["status"] = "probe_failed"
    result["account_login_attempted"] = False
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "invalid_keybag_rejected"
                     and result.get("expected_invalid_keybag_rejected") is True
                     and result.get("expected_invalid_diversity_rejected") is True else 2)
