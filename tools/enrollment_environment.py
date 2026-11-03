"""Publish only bounded, account-free probe results; discard native diagnostics."""
import json
import os
import subprocess

BOOLS = {
    "account_credentials_supplied", "account_login_attempted", "enrollment_created",
    "decryption_proven", "accessibility_trusted", "console_user_session",
    "app_store_installed", "app_store_launched",
}
COUNTS = {"window_count", "nodes_examined", "text_fields", "secure_fields"}
def clean(value):
    if not isinstance(value, dict) or value.get("schema") != "ipa-lab-enrollment-environment-v1":
        raise ValueError("invalid_probe")
    result = {"schema": value["schema"], "status": "probe_complete"}
    for key in BOOLS:
        if key in value and type(value[key]) is bool:
            result[key] = value[key]
    if value.get("architecture") in {"arm64", "other"}:
        result["architecture"] = value["architecture"]
    if value.get("status") == "app_store_not_found":
        result["status"] = "app_store_not_found"
    for key in ("state_before", "state_after"):
        if isinstance(value.get(key), dict):
            result[key] = {k: v for k, v in value[key].items()
                           if k in {"native_sidb", "native_sids", "shared_sidb"} and type(v) is bool}
    for key in ("ui_before", "ui_after_welcome", "ui_after_store_menu", "ui_after"):
        if isinstance(value.get(key), dict):
            result[key] = {k: v for k, v in value[key].items()
                           if (k in COUNTS and type(v) is int and 0 <= v <= 512)
                           or (k in {"sign_in_control_found", "scan_limited", "sign_in_label_seen", "welcome_seen", "continue_control_found", "security_prompt"} and type(v) is bool)}
            labels = value[key].get("known_labels", [])
            if isinstance(labels, list):
                result[key]["known_labels"] = sorted({x for x in labels if type(x) is str and
                                                     x in {"sign_in", "welcome", "continue", "account", "store"}})
            roles = value[key].get("roles", {})
            if isinstance(roles, dict):
                names = {"AXWindow", "AXGroup", "AXButton", "AXStaticText", "AXTextField", "AXWebArea",
                         "AXMenuBar", "AXMenuBarItem", "AXMenu", "AXMenuItem", "AXScrollArea", "AXImage", "other"}
                result[key]["roles"] = {k: v for k, v in roles.items()
                                        if k in names and type(v) is int and 0 <= v <= 512}
    press = value.get("sign_in_press_result")
    if type(press) is int and -26000 <= press <= 0:
        result["sign_in_press_result"] = press
    return result

def main():
    result = {"status": "probe_failed", "enrollment_created": False, "decryption_proven": False}
    if os.environ.get("GITHUB_ACTIONS") != "true":
        result["status"] = "requires_github_actions"
    else:
        try:
            run = subprocess.run(["./enrollment-environment", "--open-signin"],
                                 capture_output=True, text=True, timeout=100, stdin=subprocess.DEVNULL)
            if run.returncode == 0 and len(run.stdout) <= 16384:
                result = clean(json.loads(run.stdout))
        except subprocess.TimeoutExpired:
            result["status"] = "probe_timeout"
        except Exception:
            pass
    output = json.dumps(result, sort_keys=True)
    print(output)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            fence = chr(96) * 3
            summary.write("Account-free native App Store capability probe. No enrollment or decryption proof.\n\n"
                          + fence + "json\n" + output + "\n" + fence + "\n")
    return 0 if result["status"] in {"probe_complete", "app_store_not_found"} else 2

if __name__ == "__main__":
    raise SystemExit(main())
