"""Classify rejection of a fixed invalid keybag; no login or server authorization."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from machine_enrollment import clean

def run():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean(None)
    binary = str(Path("native-machine-enrollment").resolve())
    with tempfile.TemporaryDirectory(prefix="ipa-lab-import-") as tmp:
        report = Path(tmp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true", "HOME": os.environ.get("HOME", tmp)}
        child = subprocess.Popen([binary, "--import-probe", str(report)], env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            child.wait(timeout=45)
            if child.returncode or not report.is_file() or report.stat().st_size > 16384:
                return clean(None)
            return clean(json.loads(report.read_text()))
        except subprocess.TimeoutExpired:
            return clean({"status": "native_timeout"})
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()

if __name__ == "__main__":
    try:
        result = run()
    except Exception:
        result = clean(None)
    result["account_login_attempted"] = False
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "invalid_keybag_rejected"
                     and result.get("expected_invalid_keybag_rejected") is True else 2)
