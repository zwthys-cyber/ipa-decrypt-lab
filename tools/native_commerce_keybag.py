"""Bounded account-free CommerceKit IPC probe; never publish generated sync data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from machine_enrollment import native_command, run_private
from native_keybag import DOMAINS, STATE_KEYS

STATUSES = {"framework_unavailable", "interface_unavailable", "synthetic_account_unavailable",
    "service_request_failed", "service_reply_timeout", "synthetic_sync_ready",
    "malformed_service_reply", "native_exception", "native_timeout", "native_process_failed", "probe_failed"}
BOOLS = {"framework_loaded", "service_class_present", "client_class_present", "account_class_present",
    "synthetic_account_verified", "abi_verified", "synthetic_request_attempted", "reply_received",
    "transport_error_received", "service_success", "need_diversitybag", "synthetic_sync_present",
    "error_present", "error_mentions_entitlement", "error_mentions_permission", "error_mentions_account",
    "error_mentions_connection", "running_as_root", "loader_mentions_missing",
    "loader_mentions_architecture", "loader_mentions_signature", "process_mentions_assertion",
    "process_mentions_bundle", "process_mentions_application", "process_mentions_initialization", "process_mentions_library"}

def clean(value):
    result = dict(schema="ipa-lab-commerce-keybag-v1", status="probe_failed",
        account_login_attempted=False, authorization_request_attempted=False,
        keybag_import_attempted=False, enrollment_created=False, decryption_proven=False)
    if type(value) is not dict:
        return result
    if type(value.get("status")) is str and value["status"] in STATUSES:
        result["status"] = value["status"]
    for key in BOOLS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key in ("error_domain", "underlying_error_domain"):
        if type(value.get(key)) is str and value[key] in DOMAINS:
            result[key] = value[key]
    if type(value.get("native_exit_code")) is int and -128 <= value["native_exit_code"] <= 255:
        result["native_exit_code"] = value["native_exit_code"]
    if type(value.get("native_phase")) is str and value["native_phase"] in {"started", "loading_framework", "framework_loaded", "account_constructed", "service_connected", "request_sent"}:
        result["native_phase"] = value["native_phase"]
    for key in ("error_code", "underlying_error_code", "fairplay_status"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            result[key] = value[key]
    if type(value.get("transaction_type")) is int and value["transaction_type"] == 2:
        result["transaction_type"] = 2
    for key in ("state_before", "state_after"):
        if type(value.get(key)) is dict:
            result[key] = {k: value[key][k] for k in STATE_KEYS if type(value[key].get(k)) is bool}
    if result["status"] == "synthetic_sync_ready" and not (
        all(result.get(k) is True for k in ("framework_loaded", "service_class_present",
            "synthetic_account_verified", "abi_verified", "synthetic_request_attempted",
            "reply_received", "service_success", "synthetic_sync_present"))
        and result.get("error_present") is False and result.get("transport_error_received") is False
        and type(result.get("need_diversitybag")) is bool and result.get("transaction_type") == 2):
        result["status"] = "probe_failed"
    return result

def probe(user, sample):
    with tempfile.TemporaryDirectory(prefix="ipa-lab-commerce-") as temp:
        report = Path(temp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", temp), "GITHUB_ACTIONS": "true"}
        argv = native_command(str(Path("native-commerce-keybag").resolve()), report, env, user) + [sample]
        try:
            code, out, err = run_private(argv, env, timeout=35)
        except subprocess.TimeoutExpired:
            return clean({"status": "native_timeout"})
        if code or not report.is_file() or report.stat().st_size > 16384:
            partial = json.loads(report.read_text()) if report.is_file() and report.stat().st_size <= 16384 else {}
            partial.update(status="native_process_failed", native_exit_code=code)
            diagnostic = (out + err)[:32768].lower()
            for key, terms in {
                "assertion": (b"assert",), "bundle": (b"bundle",),
                "application": (b"nsapplication", b"application"),
                "initialization": (b"initializ",),
                "library": (b"library", b"dyld", b"image not found"),
            }.items():
                partial["process_mentions_" + key] = any(term in diagnostic for term in terms)
            return clean(partial)
        result = clean(json.loads(report.read_text()))
        if result.get("running_as_root") is not (user == "root"):
            result["status"] = "probe_failed"
        return result

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    failed = False
    for user in ("runner", "root"):
        for sample in ("zero", "nonzero"):
            try:
                result = probe(user, sample)
            except Exception:
                result = clean(None)
            result.update(native_user=user, synthetic_account_case=sample)
            print(json.dumps(result, sort_keys=True), flush=True)
            failed |= result["status"] in {"probe_failed", "native_process_failed", "native_timeout",
                "native_exception", "malformed_service_reply"}
    return 2 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
