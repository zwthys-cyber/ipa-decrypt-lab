"""Inspect native signing rules and sign synthetic bytes, without authorizing a machine."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from native_keybag import DOMAINS

STATUSES = {"interface_unavailable", "policy_unavailable", "signing_failed", "signature_ready",
            "signature_not_requested", "native_exception", "probe_failed", "probe_timeout"}
FLAGS = {"endpoint_supported", "native_default_mescal_one", "sap_policy_matches", "action_policy_matches",
         "policy_checked", "signing_attempted", "signing_result_present", "signature_present",
         "signature_valid", "body_unchanged", "destination_unchanged", "other_headers_unchanged", "error_present"}

def clean(value):
    r = {"schema": "ipa-lab-native-signing-v1", "status": "probe_failed",
         "account_login_attempted": False, "authorization_request_attempted": False,
         "enrollment_created": False, "decryption_proven": False}
    if type(value) is not dict:
        return r
    if type(value.get("status")) is str and value["status"] in STATUSES:
        r["status"] = value["status"]
    for key in FLAGS:
        if type(value.get(key)) is bool:
            r[key] = value[key]
    if type(value.get("error_domain")) is str and value["error_domain"] in DOMAINS:
        r["error_domain"] = value["error_domain"]
    for key in ("error_code", "fairplay_status"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            r[key] = value[key]
    if r["status"] in {"signature_ready", "signature_not_requested"}:
        if not all(r.get(k) is True for k in ("endpoint_supported", "policy_checked", "signing_attempted",
                "body_unchanged", "destination_unchanged", "other_headers_unchanged")) or r.get("error_present") is not False:
            r["status"] = "probe_failed"
        elif r["status"] == "signature_ready" and not all(r.get(k) is True for k in ("signature_present", "signature_valid")):
            r["status"] = "probe_failed"
        elif r["status"] == "signature_not_requested" and not all(r.get(k) is False for k in
                ("signature_present", "signature_valid", "sap_policy_matches", "action_policy_matches")):
            r["status"] = "probe_failed"
    return r

def run():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean(None)
    binary = str(Path("native-request-signing").resolve())
    with tempfile.TemporaryDirectory(prefix="ipa-lab-signing-") as directory:
        report = Path(directory) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "HOME": directory, "GITHUB_ACTIONS": "true"}
        process = subprocess.Popen([binary, str(report)], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            process.wait(timeout=150)
            if process.returncode or not report.is_file() or report.stat().st_size > 16384:
                return clean(None)
            return clean(json.loads(report.read_text()))
        except subprocess.TimeoutExpired:
            return clean({"status": "probe_timeout"})
        except Exception:
            return clean(None)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

if __name__ == "__main__":
    result = run()
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] in {"signature_ready", "signature_not_requested"} else 2)
