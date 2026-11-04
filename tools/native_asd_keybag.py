"""Account-free local App Store daemon request; discard raw process output."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from native_keybag import DOMAINS, STATE_KEYS

STATUSES = {"interface_unavailable", "synthetic_sync_ready", "service_request_failed",
            "native_exception", "probe_failed", "probe_timeout"}
BOOLS = {"error_mentions_entitlement", "error_mentions_permission", "error_mentions_account", "error_mentions_connection", "framework_loaded", "service_class_present", "abi_verified",
         "synthetic_request_attempted", "synthetic_sync_present", "error_present"}

def clean(value):
    report = {"schema": "ipa-lab-asd-keybag-v1", "status": "probe_failed",
              "account_login_attempted": False, "authorization_request_attempted": False,
              "keybag_import_attempted": False, "enrollment_created": False, "decryption_proven": False}
    if type(value) is not dict:
        return report
    if type(value.get("status")) is str and value["status"] in STATUSES:
        report["status"] = value["status"]
    for key in BOOLS:
        if type(value.get(key)) is bool:
            report[key] = value[key]
    if type(value.get("error_domain")) is str and value["error_domain"] in DOMAINS:
        report["error_domain"] = value["error_domain"]
    if type(value.get("underlying_error_domain")) is str and value["underlying_error_domain"] in DOMAINS:
        report["underlying_error_domain"] = value["underlying_error_domain"]
    for key in ("error_code", "fairplay_status", "underlying_error_code"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            report[key] = value[key]
    for key in ("state_before", "state_after"):
        if type(value.get(key)) is dict:
            report[key] = {k: value[key][k] for k in STATE_KEYS if type(value[key].get(k)) is bool}
    if report["status"] == "synthetic_sync_ready" and not (
            all(report.get(k) is True for k in ("framework_loaded", "service_class_present",
                "abi_verified", "synthetic_request_attempted", "synthetic_sync_present"))
            and report.get("error_present") is False):
        report["status"] = "probe_failed"
    return report

def probe(kind):
    if kind not in {"zero", "nonzero"}:
        return clean({})
    with tempfile.TemporaryDirectory(prefix="ipa-lab-asd-") as tmp:
        path = Path(tmp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        process = subprocess.Popen([str(Path("native-asd-keybag").resolve()), str(path), kind],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            code = process.wait(timeout=35)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            return clean({"status": "probe_timeout"})
        if code or not path.is_file() or path.stat().st_size > 65536:
            return clean({})
        return clean(json.loads(path.read_text()))

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        reports = []
        for kind in ("zero", "nonzero"):
            report = probe(kind)
            report["synthetic_account_kind"] = kind
            reports.append(report)
    except Exception:
        reports = [clean({})]
    for report in reports:
        print(json.dumps(report, sort_keys=True))
    # Unavailable service is a recorded diagnostic outcome, not enrollment success.
    return 0 if all(report["status"] in {"synthetic_sync_ready", "service_request_failed", "interface_unavailable"} for report in reports) else 2

if __name__ == "__main__":
    raise SystemExit(main())
