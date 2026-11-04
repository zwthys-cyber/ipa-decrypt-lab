"""Account-free native keybag prerequisites with a strict public report schema."""
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

MODES = {"interfaces", "context", "kbsync", "parameters", "public_bag", "request"}
STATUSES = {"interface_unavailable", "interfaces_checked", "context_ready", "context_failed",
            "synthetic_sync_ready", "synthetic_sync_failed", "native_exception", "probe_failed",
            "native_process_failed", "probe_timeout", "synthetic_parameters_ready",
            "synthetic_parameters_failed", "public_bag_ready", "public_bag_failed",
            "synthetic_request_ready", "synthetic_request_failed"}
SPECS = {
    "AMSKeybag": {"+sharedInstance", "-init", "-fairplayContextWithError:",
        "-keybagSyncDataWithAccountID:transactionType:error:", "-keybagSyncData:transactionType:outError:",
        "-importKeybagWithData:error:", "-importKeybagData:outError:", "-resetContext"},
    "AMSFairPlayContext": {"-init", "-fairplayContextIDWithError:", "-destroyContext"},
    "AMSAuthorizeMachineTask": {"+createBagForSubProfile", "+bagSubProfile",
        "-initWithAccount:authorizeReason:bag:", "-_buildRequestParametersWithError:",
        "-performAuthorization", "-performDeauthorization"},
    "ASDFairPlayService": {"+defaultService", "-generateKeybagRequestForDSID:error:", "-importKeybag:error:"},
    "ACAccount": {"+ams_createEphemeralAccount", "-ams_setDSID:", "-ams_DSID", "-ams_setPassword:",
        "-ams_password", "-ams_isEphemeralAccount", "-ams_setStorefront:", "-ams_setRawPassword:"},
    "AMSBag": {"+bagForProfile:profileVersion:", "-URLForKey:"},
    "AMSPromise": {"-resultWithError:", "-addFinishBlock:"},
}
DOMAINS = {"AMSErrorDomain", "ASDErrorDomain", "SSErrorDomain", "NSCocoaErrorDomain",
           "NSPOSIXErrorDomain", "NSOSStatusErrorDomain", "NSURLErrorDomain", "other"}
STATE_KEYS = {"fpsd_sidb", "fpsd_sids", "shared_sidb", "shared_sids"}

def clean(value):
    r = {"schema": "ipa-lab-native-keybag-v1", "status": "probe_failed",
         "account_login_attempted": False, "enrollment_created": False, "decryption_proven": False}
    if type(value) is not dict:
        return r
    if type(value.get("mode")) is str and value["mode"] in MODES:
        r["mode"] = value["mode"]
    if type(value.get("status")) is str and value["status"] in STATUSES:
        r["status"] = value["status"]
    for key in ("ams_loaded", "abi_verified", "context_ready", "error_present",
                "sync_data_present", "synthetic_account_id", "ephemeral_account", "guid_is_six_bytes",
                "owner_is_synthetic", "machine_name_present", "parameter_names_valid",
                "bag_url_present", "endpoint_supported", "endpoint_query_present",
                "owner_field_present", "account_dsid_is_synthetic", "token_is_synthetic", "need_div_zero",
                "need_div_one", "request_present", "request_is_post", "request_body_is_plist",
                "sap_header_present", "anisette_header_present", "secure_token_provider_used"):
        if type(value.get(key)) is bool:
            r[key] = value[key]
    if type(value.get("error_domain")) is str and value["error_domain"] in DOMAINS:
        r["error_domain"] = value["error_domain"]
    for key in ("error_code", "fairplay_status", "native_exit_code"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            r[key] = value[key]
    n = value.get("sync_data_length")
    if type(n) is int and 1 <= n <= 1048576:
        r["sync_data_length"] = n
    if type(value.get("transaction_type")) is int and value["transaction_type"] == 1:
        r["transaction_type"] = 1
    for key in ("state_before", "state_after"):
        v = value.get(key)
        if type(v) is dict:
            r[key] = {k: v[k] for k in STATE_KEYS if type(v.get(k)) is bool}
    interfaces = value.get("interfaces")
    if type(interfaces) is dict:
        r["interfaces"] = {}
        for name, selectors in SPECS.items():
            v = interfaces.get(name)
            if type(v) is not dict or type(v.get("present")) is not bool:
                continue
            entry = {"present": v["present"], "methods": {}}
            methods = v.get("methods", {})
            if type(methods) is dict:
                for sel in selectors:
                    encoding = methods.get(sel)
                    if encoding is None:
                        entry["methods"][sel] = None
                    elif type(encoding) is str and re.fullmatch(r"[v@:#?^BIQcCisSlLqfd0-9rnNoORV+\-]{1,100}", encoding):
                        entry["methods"][sel] = encoding
            r["interfaces"][name] = entry
    keys = value.get("bag_keys")
    if type(keys) is dict:
        allowed = {"AMSBagKeyAuthorizeMachineURL": {"authorizeMachine", "authorize-machine"},
                   "AMSBagKeyDeauthorizeMachineURL": {"deauthorizeMachine", "deauthorize-machine"}}
        r["bag_keys"] = {k: keys[k] for k, vals in allowed.items()
                         if type(keys.get(k)) is str and keys[k] in vals}
    names = value.get("parameter_names")
    if type(names) is list:
        r["parameter_names"] = sorted({n for n in names if type(n) is str and re.fullmatch(r"[A-Za-z][A-Za-z-]{0,63}", n)})[:24]
    route = value.get("public_endpoint_route")
    if r.get("mode") == "public_bag" and type(route) is str and re.fullmatch(r"/[A-Za-z/._-]{1,158}", route):
        r["public_endpoint_route"] = route
    host, path = value.get("endpoint_host"), value.get("endpoint_path")
    if type(host) is str and re.fullmatch(r"(buy|p[0-9]{1,3}-buy|finance-app)\.itunes\.apple\.com", host):
        r["endpoint_host"] = host
    if path in ("/WebObjects/MZFinance.woa/wa/authorizeMachine", "/WebObjects/MZFinance.woa/wa/authorizeMachine/", "/commerce/machine/authorize"):
        r["endpoint_path"] = path
    if r["status"] == "synthetic_request_ready" and not (
        all(r.get(k) is True for k in ("abi_verified", "ephemeral_account", "request_present",
            "request_is_post", "request_body_is_plist", "token_is_synthetic", "owner_is_synthetic", "endpoint_supported"))
        and r.get("error_present") is False):
        r["status"] = "probe_failed"
    if r["status"] == "synthetic_parameters_ready" and not (
        all(r.get(k) is True for k in ("abi_verified", "ephemeral_account", "sync_data_present",
            "guid_is_six_bytes", "owner_is_synthetic", "machine_name_present", "parameter_names_valid", "token_is_synthetic"))
        and r.get("sync_data_length", 0) > 0 and r.get("error_present") is False):
        r["status"] = "probe_failed"
    if r["status"] == "public_bag_ready" and not (
        r.get("abi_verified") is True and r.get("bag_url_present") is True and r.get("error_present") is False):
        r["status"] = "probe_failed"
    if r["status"] == "context_ready" and not (
        r.get("abi_verified") is True and r.get("context_ready") is True and r.get("error_present") is False):
        r["status"] = "probe_failed"
    if r["status"] == "synthetic_sync_ready" and not (
        r.get("abi_verified") is True and r.get("sync_data_present") is True
        and r.get("synthetic_account_id") is True and r.get("transaction_type") == 1
        and r.get("sync_data_length", 0) > 0 and r.get("error_present") is False):
        r["status"] = "probe_failed"
    return r

def environment():
    return {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}

def probe(mode):
    if mode not in MODES:
        raise ValueError("unsupported mode")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-keybag-") as tmp:
        path = Path(tmp) / "report.json"
        try:
            p = subprocess.run(["./native-keybag", mode, str(path)], env=environment(),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            if p.returncode != 0:
                return clean({"mode": mode, "status": "native_process_failed", "native_exit_code": p.returncode})
            if not path.is_file() or path.stat().st_size > 65536:
                return clean({"mode": mode})
            return clean(json.loads(path.read_text()))
        except subprocess.TimeoutExpired:
            return clean({"mode": mode, "status": "probe_timeout"})
        except (OSError, ValueError):
            return clean({"mode": mode})

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS is required")
    arch = platform.machine()
    r = {"schema": "ipa-lab-native-keybag-matrix-v1",
         "architecture": arch if arch in {"arm64", "x86_64"} else "other",
         "cases": [probe(mode) for mode in ("interfaces", "context", "kbsync", "parameters", "public_bag", "request")],
         "account_login_attempted": False, "enrollment_created": False, "decryption_proven": False}
    print(json.dumps(r, sort_keys=True))
    if any(c["status"] in {"probe_failed", "native_process_failed", "probe_timeout", "native_exception"}
           for c in r["cases"]):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
