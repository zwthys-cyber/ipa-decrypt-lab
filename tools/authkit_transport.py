"""Account-free comparison of default and identified AuthKit daemon clients."""
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys

BOOLS = {"explicit_client_identifier", "bundle_identifier_present", "bag_selector_present",
         "identifier_initializer_present", "error_present", "xpc_connection_invalid",
         "xpc_connection_interrupted", "missing_entitlement", "code_signing_requirement",
         "lookup_failed", "service_missing", "connection_invalidated", "sandbox_denied",
         "connection_rejected", "callback_completed", "bag_result_present",
         "connection_object_present", "raw_xpc_connection_present", "service_name_recognized",
         "peer_pid_available", "invalidation_reason_api_present", "invalidation_reason_present",
         "reason_missing_entitlement", "reason_code_signing_requirement", "reason_lookup_failed",
         "reason_service_missing", "reason_connection_invalidated", "reason_sandbox_denied",
         "reason_connection_rejected", "reason_internal_authkit_entitlement_named",
         "reason_peer_code_requirement", "reason_peer_cancelled",
         "signature_metadata_available", "declared_internal_authkit_entitlement", "native_process_signalled",
         "proxy_trace_installed", "effective_user_is_root"}
STATUSES = {"interface_unavailable", "transport_timeout", "transport_rejected", "bag_fetch_succeeded",
            "empty_result", "native_exception", "probe_failed", "requires_github_macos", "native_process_failed"}
DOMAINS = {"NSCocoaErrorDomain", "AKAuthenticationError", "AKAuthenticationServerError",
           "NSPOSIXErrorDomain", "NSURLErrorDomain"}
SERVICES = {"com.apple.ak.auth.xpc", "com.apple.ak.anisette.xpc",
            "com.apple.ak.authorizationservices.xpc", "com.apple.akd"}

REASON_TERMS = set("peer cancelled canceled client server signature entitlement requirement identity connection invalid terminated rejected lookup endpoint process exited code signing sandbox bootstrap interrupted transport authorization authentication permission denied error unavailable unsupported resume current remote closed unknown active still not yet pending no invalidation reason suspended never attempted connected disconnected activated activation".split())

def clean(value, nested=False):
    result = {"schema": "ipa-lab-authkit-transport-v1", "status": "probe_failed",
              "account_login_attempted": False, "enrollment_created": False, "decryption_proven": False}
    if not isinstance(value, dict):
        return result
    if type(value.get("status")) is str and value["status"] in STATUSES:
        result["status"] = value["status"]
    for key in BOOLS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    if type(value.get("error_domain")) is str and value["error_domain"] in DOMAINS:
        code = value.get("error_code")
        if type(code) is int and -999999 <= code <= 999999:
            result.update(error_domain=value["error_domain"], error_code=code)
    if not nested and type(value.get("observed_auth_proxy_requests")) is int and 0 <= value["observed_auth_proxy_requests"] <= 32:
        result["observed_auth_proxy_requests"] = value["observed_auth_proxy_requests"]
    if not nested and type(value.get("observed_proxy_failures")) is list:
        result["observed_proxy_failures"] = [clean(item, nested=True) for item in value["observed_proxy_failures"][:4] if type(item) is dict]
    if type(value.get("invalidation_reason_terms")) is list:
        result["invalidation_reason_terms"] = sorted({term for term in value["invalidation_reason_terms"]
            if type(term) is str and term in REASON_TERMS})
    if type(value.get("native_exit_code")) is int and -128 <= value["native_exit_code"] <= 255:
        result["native_exit_code"] = value["native_exit_code"]
    if type(value.get("service_name")) is str and value["service_name"] in SERVICES:
        result["service_name"] = value["service_name"]
    if value.get("sdk_xpc_invalid_code") == 4099:
        result["sdk_xpc_invalid_code"] = 4099
    if result["status"] == "bag_fetch_succeeded" and not (
        result.get("callback_completed") is True and result.get("bag_result_present") is True
        and result.get("error_present") is False
    ):
        result["status"] = "probe_failed"
    return result

def environment():
    return {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}

def classify_connection_text(text):
    if type(text) is not str or len(text) > 1048576:
        return {"text_classification_available": False}
    text = text.lower()
    denial = "entitlement" in text and any(phrase in text for phrase in (
        "missing", "not entitled", "not have", "lacks", "not present", "not allowed", "denied"))
    return {"text_classification_available": True,
            "entitlement_denial_phrase": denial,
            "internal_authkit_entitlement_named": "com.apple.authkit.client.internal" in text,
            "own_client_named": "authkittransport" in text or "authkit-transport" in text,
            "code_requirement_phrase": "code signing requirement" in text or "codesigning requirement" in text}

def daemon_diagnostic():
    result = {"status": "query_failed", "events": 0, "entitlement_denial_events": 0,
              "internal_authkit_entitlement_events": 0, "own_client_denial_events": 0,
              "own_client_internal_entitlement_denial_events": 0}
    try:
        predicate = 'process == "akd" AND (eventMessage CONTAINS[c] "entitle" OR eventMessage CONTAINS[c] "AuthKitTransport" OR eventMessage CONTAINS[c] "authkit-transport")'
        run = subprocess.run(["/usr/bin/log", "show", "--last", "1m", "--style", "json",
            "--info", "--debug", "--predicate", predicate],
            capture_output=True, text=True, timeout=10, env=environment())
        if run.returncode or len(run.stdout) > 1048576:
            return result
        events = json.loads(run.stdout)
        if type(events) is not list or len(events) > 1000:
            return result
        result["status"] = "queried"
        for event in events:
            if type(event) is not dict or Path(event.get("processImagePath", "")).name != "akd":
                continue
            flags = classify_connection_text(event.get("eventMessage"))
            result["events"] += 1
            denied = flags.get("entitlement_denial_phrase", False)
            internal = flags.get("internal_authkit_entitlement_named", False)
            own = flags.get("own_client_named", False)
            result["entitlement_denial_events"] += int(denied)
            result["internal_authkit_entitlement_events"] += int(internal)
            result["own_client_denial_events"] += int(own and denied)
            result["own_client_internal_entitlement_denial_events"] += int(own and internal and denied)
    except Exception:
        pass
    return result

def probe(binary, mode, scope="user"):
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean({"status": "requires_github_macos"})
    if mode not in {"default", "named"} or scope not in {"user", "root_gui"}:
        return clean({})
    try:
        command = [str(Path(binary).resolve()), mode]
        if scope == "root_gui":
            command = ["/usr/bin/sudo", "-n", "/bin/launchctl", "asuser", str(os.getuid()),
                       "/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "GITHUB_ACTIONS=true"] + command
        run = subprocess.run(command, stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=20, env=environment())
        if run.returncode:
            return clean({"status": "native_process_failed", "native_exit_code": run.returncode,
                          "native_process_signalled": run.returncode < 0})
        if len(run.stdout) > 8192:
            return clean({})
        result = clean(json.loads(run.stdout))
        result["stderr_classification"] = classify_connection_text(run.stderr)
        return result
    except Exception:
        return clean({})

def service_metadata():
    result = {}
    for scope in ("gui", "user"):
        try:
            run = subprocess.run(["/bin/launchctl", "print", f"{scope}/{os.getuid()}/com.apple.akd"],
                capture_output=True, timeout=5, env=environment())
            result[scope + "_akd_registered"] = run.returncode == 0
        except Exception:
            result[scope + "_akd_registered"] = False
    path = Path("/System/Library/LaunchAgents/com.apple.akd.plist")
    result["akd_launch_agent_plist_present"] = path.is_file()
    if path.is_file():
        try:
            values = plistlib.loads(path.read_bytes())
            services = values.get("MachServices", {})
            result["known_advertised_services"] = sorted(name for name in SERVICES if name in services)
        except Exception:
            pass
    for label, path in {
        "app_store": "/System/Applications/App Store.app",
        "client": "./AuthKitTransport.app",
    }.items():
        try:
            run = subprocess.run(["/usr/bin/codesign", "-d", "--entitlements", ":-", path],
                capture_output=True, timeout=5, env=environment())
            if run.returncode == 0 and len(run.stdout) <= 65536:
                values = plistlib.loads(run.stdout)
                keys = {key: type(value) is bool and value for key, value in values.items()
                        if type(key) is str and key.startswith(("com.apple.authkit.", "com.apple.private.authkit."))}
                result[label + "_authkit_entitlements"] = keys
        except Exception:
            pass
    return result

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        print(json.dumps(clean({"status": "requires_github_macos"})))
        return 2
    rows = []
    for label, binary in (("command_line", "./authkit-transport"),
                          ("own_app_bundle", "./AuthKitTransport.app/Contents/MacOS/AuthKitTransport")):
        for mode in ("default", "named"):
            row = probe(binary, mode)
            row["container"] = label
            rows.append(row)
    for mode in ("default", "named"):
        row = probe("./AuthKitTransport.app/Contents/MacOS/AuthKitTransport", mode, scope="root_gui")
        row["container"] = "own_app_root_in_user_gui"
        rows.append(row)
    report = {"schema": "ipa-lab-authkit-transport-comparison-v1", "probes": rows,
              "metadata": service_metadata(), "daemon_diagnostic": daemon_diagnostic(),
              "account_login_attempted": False,
              "enrollment_created": False, "decryption_proven": False}
    output = json.dumps(report, sort_keys=True)
    print(output)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(chr(96) * 3 + "json\n" + output + "\n" + chr(96) * 3 + "\n")
    return 2 if any(row["status"] in {"probe_failed", "requires_github_macos", "native_exception"} for row in rows) else 0

if __name__ == "__main__":
    raise SystemExit(main())
