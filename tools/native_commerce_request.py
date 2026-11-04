"""Construct a synthetic CommerceKit URL request without sending it."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from machine_enrollment import run_private
from native_commerce_keybag import clean as clean_metadata

SCHEMA = "ipa-lab-commerce-request-v1"
STATUSES = {"interface_unavailable", "framework_unavailable", "synthetic_account_unavailable",
    "body_unverified", "request_unavailable", "request_shape_unverified", "request_constructed",
    "native_exception", "native_timeout", "native_process_failed", "probe_failed"}
REQUIRED = {"framework_loaded", "synthetic_account_verified", "synthetic_token_verified",
    "body_abi_verified", "body_created", "body_sync_present", "body_token_matches",
    "body_needdiv_valid", "body_parameter_names_valid", "request_abi_verified",
    "request_created", "request_https", "request_host_allowed", "request_path_allowed",
    "request_is_post", "request_body_is_plist", "body_sync_preserved", "body_token_preserved",
    "body_needdiv_preserved"}
FLAGS = REQUIRED | {"body_machine_name_present", "need_diversitybag", "request_user_agent_configurator",
    "request_ds_header_matches", "request_has_anisette", "body_owner_matches_synthetic",
    "body_guid_is_six_bytes"}

def clean(value):
    if type(value) is not dict or value.get("schema") != SCHEMA:
        result = clean_metadata(None)
        result["schema"] = SCHEMA
        return result
    result = clean_metadata(dict(value, status="interface_unavailable"))
    result["schema"] = SCHEMA
    status = value.get("status")
    result["status"] = status if type(status) is str and status in STATUSES else "probe_failed"
    for key in FLAGS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    phase = value.get("native_phase")
    if type(phase) is str and phase in {"started", "building_body", "building_request"}:
        result["native_phase"] = phase
    else:
        result.pop("native_phase", None)
    if result["status"] == "request_constructed" and not (
            all(result.get(key) is True for key in REQUIRED)
            and result.get("error_present") is False and result.get("running_as_root") is False):
        result["status"] = "probe_failed"
    return result

def probe():
    with tempfile.TemporaryDirectory(prefix="ipa-lab-commerce-request-") as temp:
        report = Path(temp) / "report.json"
        env = {"PATH": "/usr/bin:/bin", "HOME": os.environ.get("HOME", temp), "GITHUB_ACTIONS": "true"}
        argv = [str(Path("native-commerce-request").resolve()), str(report)]
        try:
            code, _, _ = run_private(argv, env, timeout=30)
        except subprocess.TimeoutExpired:
            return clean(dict(schema=SCHEMA, status="native_timeout"))
        value = {}
        if report.is_file() and report.stat().st_size <= 16384:
            try:
                value = json.loads(report.read_text())
            except (ValueError, OSError):
                pass
        if type(value) is not dict:
            value = {}
        if code:
            value.update(schema=SCHEMA, status="native_process_failed", native_exit_code=code)
        return clean(value)

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        result = probe()
    except Exception:
        result = clean(None)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "request_constructed" else 2

if __name__ == "__main__":
    raise SystemExit(main())
