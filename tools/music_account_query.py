"""Private Music UI login/count orchestration; output only fixed metadata."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

SCHEMA = "ipa-lab-music-account-query-v1"
STATUSES = {
    "navigation_failed", "preflight_ready", "preflight_failed", "missing_credentials",
    "email_form_unavailable", "email_fill_failed", "email_submit_failed",
    "password_form_unavailable", "password_fill_failed", "password_submit_failed",
    "signin_unconfirmed", "account_menu_unavailable", "account_settings_unavailable",
    "count_not_observed", "count_retrieved", "native_timeout", "native_failed",
    "invalid_report", "unexpected_account_mutation",
}
BOOLS = {
    "credentials_used", "email_form_ready", "password_form_ready",
    "email_submit_attempted", "password_submit_attempted", "signed_in_menu_observed",
    "account_settings_invoked", "authorization_section_observed",
    "explicit_current_count_observed", "authorization_count_retrieved",
    "explicit_machine_authorization_invoked", "deauthorization_invoked",
    "security_upgrade_accepted", "accessibility_trusted",
    "synthetic_email_fill_ready", "synthetic_email_cleared",
}
COUNT_EVIDENCE = {
    "credentials_used", "email_submit_attempted", "password_submit_attempted",
    "signed_in_menu_observed", "account_settings_invoked",
    "authorization_section_observed", "explicit_current_count_observed",
    "authorization_count_retrieved",
}
FORBIDDEN = {"explicit_machine_authorization_invoked", "deauthorization_invoked", "security_upgrade_accepted"}
LABELS = {
    "sign_in", "sign_in_heading", "sign_out", "apple_account", "password", "cancel",
    "continue", "not_now", "verification", "security_upgrade", "decline_upgrade",
    "terms", "agree", "subscribe", "credentials_rejected", "computer_authorizations",
    "authorized_devices", "deauthorize_all", "account_settings",
}
ROLES = {"AXWindow", "AXSheet", "AXDialog", "AXTextField", "AXButton", "AXStaticText", "AXWebArea"}
STAGES = {"preflight", "after_email", "after_password", "account_settings"}

def clean(raw):
    if not isinstance(raw, dict):
        raw = {}
    r = {"schema": SCHEMA, "status": raw.get("status") if raw.get("status") in STATUSES else "invalid_report"}
    r.update({k: v for k, v in raw.items() if k in BOOLS and type(v) is bool})
    if any(raw.get(k) is not False for k in FORBIDDEN):
        r["status"] = "unexpected_account_mutation" if any(raw.get(k) is True for k in FORBIDDEN) else "invalid_report"
    count = raw.get("authorized_computer_count")
    valid_count = type(count) is int and 0 <= count <= 5 and all(raw.get(k) is True for k in COUNT_EVIDENCE)
    if r["status"] == "count_retrieved" and valid_count:
        r["authorized_computer_count"] = count
    else:
        r["authorization_count_retrieved"] = False
        if r["status"] == "count_retrieved":
            r["status"] = "invalid_report"
    if r["status"] == "preflight_ready" and (
        not all(raw.get(k) is True for k in ("email_form_ready", "synthetic_email_fill_ready", "synthetic_email_cleared"))
        or any(raw.get(k) is not False for k in ("credentials_used", "email_submit_attempted", "password_submit_attempted"))
    ):
        r["status"] = "invalid_report"
    screens = raw.get("screens")
    if isinstance(screens, dict):
        sanitized = {}
        for stage, screen in screens.items():
            if stage not in STAGES or not isinstance(screen, dict):
                continue
            item = {}
            for name, allowed in (("roles", ROLES), ("labels", LABELS)):
                values = screen.get(name)
                if isinstance(values, dict):
                    item[name] = {k: v for k, v in values.items()
                                  if k in allowed and type(v) is int and 0 <= v <= 320}
            sanitized[stage] = item
        r["screens"] = sanitized
    return r

def failure(status):
    return clean(dict(status=status, **{k: False for k in FORBIDDEN}))

def run(binary, preflight=False):
    data = None
    if not preflight:
        email, password = os.environ.get("APPLE_ID"), os.environ.get("APPLE_PASSWORD")
        if not email or not password:
            return failure("missing_credentials")
        data = json.dumps({"apple_id": email, "password": password}).encode()
    env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}
    if os.environ.get("HOME"):
        env["HOME"] = os.environ["HOME"]
    argv = [binary] + (["--preflight"] if preflight else [])
    process = subprocess.Popen(argv, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               env=env, start_new_session=True)
    try:
        output, _ = process.communicate(data, timeout=125)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate(timeout=5)
        return failure("native_timeout")
    finally:
        data = None
    if process.returncode:
        return failure("native_failed")
    if not output or len(output) > 65536:
        return failure("invalid_report")
    try:
        return clean(json.loads(output))
    except (ValueError, UnicodeError):
        return failure("invalid_report")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", required=True)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        result = run(str(Path(args.binary).resolve()), args.preflight)
    except Exception:
        result = failure("native_failed")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == ("preflight_ready" if args.preflight else "count_retrieved") else 2

if __name__ == "__main__":
    raise SystemExit(main())
