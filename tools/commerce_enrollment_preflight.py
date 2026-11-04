"""Exercise the actual commerce enrollment constructor with fixed input, without login or submission."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from machine_enrollment import clean, run_private
from native_commerce_request import private_identity

def probe(binary):
    with tempfile.TemporaryDirectory(prefix="ipa-lab-enrollment-preflight-") as temp:
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", temp), "GITHUB_ACTIONS": "true"}
        identity = private_identity(env)
        if identity is None:
            return clean({"status": "private_handoff_failed"})
        report = Path(temp) / "report.json"
        code, _, _ = run_private([binary, "--prepare-probe", str(report)], env, data=identity, timeout=35)
        if code or not report.is_file() or report.stat().st_size > 65536:
            return clean({"status": "native_process_failed"})
        return clean(json.loads(report.read_text()))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-binary", default="native-machine-enrollment")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        result = probe(str(Path(args.native_binary).resolve()))
    except Exception:
        result = clean({"status": "probe_failed"})
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "commerce_request_prepared" else 2

if __name__ == "__main__":
    raise SystemExit(main())
