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
         "connection_rejected", "callback_completed", "bag_result_present"}
STATUSES = {"interface_unavailable", "transport_timeout", "transport_rejected", "bag_fetch_succeeded",
            "empty_result", "native_exception", "probe_failed", "requires_github_macos"}
DOMAINS = {"NSCocoaErrorDomain", "AKAuthenticationError", "AKAuthenticationServerError",
           "NSPOSIXErrorDomain", "NSURLErrorDomain"}
def clean(value):
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

def probe(binary, mode):
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean({"status": "requires_github_macos"})
    if mode not in {"default", "named"}:
        return clean({})
    try:
        run = subprocess.run([str(Path(binary).resolve()), mode], stdin=subprocess.DEVNULL,
                             capture_output=True, text=True, timeout=20, env=environment())
        if run.returncode or len(run.stdout) > 8192:
            return clean({})
        return clean(json.loads(run.stdout))
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
    report = {"schema": "ipa-lab-authkit-transport-comparison-v1", "probes": rows,
              "metadata": service_metadata(), "account_login_attempted": False,
              "enrollment_created": False, "decryption_proven": False}
    output = json.dumps(report, sort_keys=True)
    print(output)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(chr(96) * 3 + "json\n" + output + "\n" + chr(96) * 3 + "\n")
    return 2 if any(row["status"] in {"probe_failed", "requires_github_macos", "native_exception"} for row in rows) else 0

if __name__ == "__main__":
    raise SystemExit(main())
