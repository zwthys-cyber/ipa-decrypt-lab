"""Fixed invalid-import observation. A no-reply IPC call never establishes import success."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from machine_enrollment import run_private
from native_commerce_keybag import clean as clean_sync, BOOLS
from native_keybag import DOMAINS, STATE_KEYS

SCHEMA = "ipa-lab-commerce-import-v1"
STATUSES = {"probe_failed", "framework_unavailable", "synthetic_account_unavailable",
    "interface_unavailable", "baseline_unavailable", "followup_unavailable",
    "transport_failed", "baseline_complete", "submission_unverified",
    "native_exception", "native_timeout", "native_process_failed"}
FLAGS = BOOLS | {"sync_abi_verified", "import_abi_verified", "import_call_returned",
                 "keybag_import_attempted"}
READY_FLAGS = ("reply_received", "service_success", "synthetic_sync_present")

def reply(value):
    if type(value) is not dict:
        return {"status": "probe_failed"}
    # Reuse only field sanitization; this report has no identity/ABI claim of its own.
    source = dict(value, status="service_request_failed")
    result = clean_sync(source)
    for key in ("schema", "account_login_attempted", "authorization_request_attempted",
                "keybag_import_attempted", "enrollment_created", "decryption_proven"):
        result.pop(key, None)
    candidate = value.get("status")
    if type(candidate) is str and candidate in {"service_reply_timeout", "service_request_failed",
            "malformed_service_reply"}:
        result["status"] = candidate
    if (candidate == "synthetic_sync_ready"
            and all(result.get(key) is True for key in READY_FLAGS)
            and result.get("error_present") is False
            and type(result.get("need_diversitybag")) is bool):
        result["status"] = "synthetic_sync_ready"
    return result

def clean(value, fixture):
    result = dict(schema=SCHEMA, status="probe_failed",
        account_login_attempted=False, authorization_request_attempted=False,
        import_verified=False, enrollment_created=False, decryption_proven=False)
    if fixture not in ("baseline", "invalid-both"):
        return result
    result["fixture"] = fixture
    if type(value) is not dict or value.get("fixture") != fixture or value.get("schema") != SCHEMA:
        return result
    if type(value.get("status")) is str and value["status"] in STATUSES:
        result["status"] = value["status"]
    for key in FLAGS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key in ("error_domain", "underlying_error_domain"):
        if type(value.get(key)) is str and value[key] in DOMAINS:
            result[key] = value[key]
    for key in ("error_code", "underlying_error_code", "fairplay_status"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            result[key] = value[key]
    if type(value.get("native_exit_code")) is int and -128 <= value["native_exit_code"] <= 255:
        result["native_exit_code"] = value["native_exit_code"]
    if type(value.get("native_phase")) is str and value["native_phase"] in {
            "started", "import_submitting", "import_submitted"}:
        result["native_phase"] = value["native_phase"]
    for key in ("baseline", "followup"):
        if key in value:
            result[key] = reply(value[key])
    for key in ("state_before", "state_after"):
        if type(value.get(key)) is dict:
            result[key] = {k: value[key][k] for k in STATE_KEYS if type(value[key].get(k)) is bool}
    if result["status"] in {"baseline_complete", "submission_unverified"}:
        valid = (result.get("running_as_root") is False
            and all(result.get(k) is True for k in ("framework_loaded", "synthetic_account_verified",
                "sync_abi_verified", "import_abi_verified"))
            and result.get("transport_error_received") is False
            and all(result.get(k, {}).get("status") == "synthetic_sync_ready" for k in ("baseline", "followup"))
            and all(set(result.get(k, {})) == set(STATE_KEYS) for k in ("state_before", "state_after")))
        if fixture == "invalid-both":
            valid &= (result["status"] == "submission_unverified"
                and result.get("keybag_import_attempted") is True and result.get("import_call_returned") is True)
        else:
            valid &= (result["status"] == "baseline_complete"
                and result.get("keybag_import_attempted") is False and result.get("import_call_returned") is False)
        if not valid:
            result["status"] = "probe_failed"
    return result

def probe(fixture):
    if fixture not in ("baseline", "invalid-both"):
        raise ValueError("fixed fixture required")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-commerce-import-") as temp:
        report = Path(temp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", temp), "GITHUB_ACTIONS": "true"}
        argv = [str(Path("native-commerce-import").resolve()), str(report), fixture]
        try:
            code, _, _ = run_private(argv, env, timeout=30)
        except subprocess.TimeoutExpired:
            return clean(dict(schema=SCHEMA, fixture=fixture, status="native_timeout"), fixture)
        value = {}
        if report.is_file() and report.stat().st_size <= 16384:
            try:
                value = json.loads(report.read_text())
            except (ValueError, OSError):
                pass
        if type(value) is not dict:
            value = {}
        if code:
            value.update(schema=SCHEMA, fixture=fixture, status="native_process_failed", native_exit_code=code)
        return clean(value, fixture)

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    failed = False
    for fixture in ("baseline", "invalid-both"):
        try:
            result = probe(fixture)
        except Exception:
            result = clean(None, fixture)
        print(json.dumps(result, sort_keys=True), flush=True)
        failed |= result["status"] not in {"baseline_complete", "submission_unverified"}
        if result["status"] != "baseline_complete" and fixture == "baseline":
            break
    return 2 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
