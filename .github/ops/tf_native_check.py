"""Capture native diagnostics privately and publish a strict, closed report."""
import argparse
import json
import os
from pathlib import Path
import subprocess

KEYS={"schema","status","native_udid_20","native_mac_model","native_machine_header",
      "native_identifier_length","hardware_source","private_profile_written"}
def validate(value):
    if not isinstance(value,dict) or set(value)!=KEYS:raise ValueError("tf_native_report_invalid")
    if value["schema"]!="testflight-native-preflight-v1" or value["status"] not in {
        "ready","native_context_unavailable","native_probe_stopped"}:raise ValueError("tf_native_report_invalid")
    for key in ("native_udid_20","native_mac_model","native_machine_header","private_profile_written"):
        if type(value[key]) is not bool:raise ValueError("tf_native_report_invalid")
    if type(value["native_identifier_length"]) is not int or not 0<=value["native_identifier_length"]<=128:
        raise ValueError("tf_native_report_invalid")
    if value["hardware_source"] not in ("authkit_unique_identifier","unavailable"):
        raise ValueError("tf_native_report_invalid")
    if value["status"]=="ready" and not all(value[key] for key in ("native_udid_20","native_mac_model","native_machine_header")):
        raise ValueError("tf_native_report_invalid")
    return value

STAGES = ("started", "identity", "model", "bag", "headers", "finished")
def summarize_probe(result):
    # stderr may contain private framework logs; expose only our fixed markers.
    stage = "not_started"
    for line in result.stderr.splitlines():
        for known in STAGES:
            if line == ("TF_PROBE_STAGE:" + known).encode():
                stage = known
    diagnostics = {"exit_code": max(-128, min(255, result.returncode)),
                   "stdout_bytes": min(len(result.stdout), 1048576),
                   "stage": stage}
    if len(result.stdout) > 2048:
        return None, "output_too_large", diagnostics
    try:
        value = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        return None, "process_signal" if result.returncode < 0 else "invalid_json", diagnostics
    try:
        return validate(value), "valid_report", diagnostics
    except ValueError:
        if isinstance(value, dict):
            diagnostics["missing_fields"] = sorted(KEYS - set(value))
            diagnostics["extra_field_count"] = min(len(set(value) - KEYS), 128)
            diagnostics["field_types"] = {
                key: type(value[key]).__name__ if type(value[key]) in (bool, int, str, dict, list, type(None)) else "other"
                for key in sorted(KEYS & set(value))
            }
            for key, allowed in (
                ("status", {"ready", "native_context_unavailable", "native_probe_stopped", "unavailable"}),
                ("schema", {"testflight-native-preflight-v1"}),
                ("hardware_source", {"authkit_unique_identifier", "unavailable"})):
                candidate = value.get(key)
                diagnostics[key] = candidate if type(candidate) is str and candidate in allowed else "unrecognized"
        return None, "invalid_report", diagnostics

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser();parser.add_argument("--binary",required=True);args=parser.parse_args()
    report={"schema":"testflight-prototype-v1","stage":"native_context","status":"tf_native_probe_stopped",
            "apple_login_attempted":False,"invitation_accepted":False,"downloaded":False,
            "decryption_proven":False,"hardware_values_published":False}
    try:
        result=subprocess.run([str(Path(args.binary).resolve())],stdin=subprocess.DEVNULL,capture_output=True,
                              timeout=60,env={k:os.environ[k] for k in ("HOME","PATH","LANG","RUNNER_TEMP") if k in os.environ})
        value, category, diagnostics = summarize_probe(result)
        report.update(probe_category=category, probe=diagnostics)
        if value is None: raise ValueError()
        report.update(native=value,status="tf_native_context_ready" if result.returncode==0 and value["status"]=="ready" else "tf_native_context_unavailable")
    except Exception:pass
    report.update(run_id=os.environ.get("GITHUB_RUN_ID"),source_commit=os.environ.get("GITHUB_SHA"))
    Path("tf-native-receipt.json").write_text(json.dumps(report))
    print(json.dumps(report),flush=True)
    return 0 if report["status"]=="tf_native_context_ready" else 2

if __name__=="__main__":raise SystemExit(main())
