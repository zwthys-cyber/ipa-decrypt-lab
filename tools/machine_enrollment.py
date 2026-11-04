"""Bounded private Store login and one native machine-authorization request."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
from native_keybag import DOMAINS, STATE_KEYS

STATUSES = {"invalid_private_input", "request_preparation_failed", "request_timeout", "request_stopped",
    "response_not_plist", "keybag_not_issued", "import_interface_unavailable",
    "keybag_imported_model_unverified", "keybag_import_failed", "native_exception", "probe_failed",
    "missing_credentials", "login_failed", "login_ambiguous", "login_timeout", "native_timeout",
    "native_process_failed", "private_handoff_failed"}
BOOLS = {"authorization_request_attempted", "ephemeral_account", "session_identity_verified",
    "redirect_blocked", "response_oversized", "error_present", "apple_failure_present",
    "dialog_present", "keybag_present", "keybag_import_succeeded", "redirect_seen",
    "redirect_query_supported", "redirect_method_post", "redirect_https", "storefront_header_present",
    "message_mentions_sign_in", "message_mentions_password", "message_mentions_verification_code", "message_mentions_computer_limit"}

def clean(value):
    r = {"schema": "ipa-lab-machine-enrollment-v1", "status": "probe_failed",
         "enrollment_created": False, "decryption_proven": False}
    if type(value) is not dict:
        return r
    if type(value.get("status")) is str and value["status"] in STATUSES:
        r["status"] = value["status"]
    for key in BOOLS:
        if type(value.get(key)) is bool:
            r[key] = value[key]
    for key, choices in {
        "redirect_host_kind": {"buy", "pod_buy", "finance_app", "other"},
        "redirect_path_kind": {"authorize_exact", "authorize_slash", "legacy", "legacy_slash", "other"},
    }.items():
        if type(value.get(key)) is str and value[key] in choices:
            r[key] = value[key]
    if type(value.get("session_cookie_count")) is int and 0 <= value["session_cookie_count"] <= 128:
        r["session_cookie_count"] = value["session_cookie_count"]
    if type(value.get("approved_redirect_count")) is int and 0 <= value["approved_redirect_count"] <= 1:
        r["approved_redirect_count"] = value["approved_redirect_count"]
    for key in ("error_code", "apple_failure_code", "fairplay_status"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            r[key] = value[key]
    if type(value.get("http_status")) is int and 100 <= value["http_status"] <= 599:
        r["http_status"] = value["http_status"]
    if type(value.get("error_domain")) is str and value["error_domain"] in DOMAINS:
        r["error_domain"] = value["error_domain"]
    for key in ("state_before", "state_after"):
        if type(value.get(key)) is dict:
            r[key] = {k: value[key][k] for k in STATE_KEYS if type(value[key].get(k)) is bool}
    if r["status"] == "keybag_imported_model_unverified" and not (
        all(r.get(k) is True for k in ("authorization_request_attempted", "session_identity_verified",
                                      "keybag_present", "keybag_import_succeeded"))
        and r.get("http_status") == 200 and r.get("error_present") is False
        and r.get("apple_failure_present") is False and r.get("redirect_blocked") is False
        and r.get("response_oversized") is False):
        r["status"] = "probe_failed"
    return r

def run_private(argv, env, *, data=None, timeout=120):
    p = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(input=data, timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.communicate()
        raise

def trial(login_binary, native_binary, purpose="signIn", session_context="token"):
    if purpose not in {"signIn", "machineAuthorize", "machineSession"} or session_context not in {"token", "cookies", "storefront", "store"}:
        return clean({"status": "invalid_private_input"})
    email, password = os.environ.get("APPLE_ID"), os.environ.get("APPLE_PASSWORD")
    if not email or not password:
        return clean({"status": "missing_credentials"})
    with tempfile.TemporaryDirectory(prefix="ipa-lab-machine-enrollment-") as tmp:
        root = Path(tmp)
        handoff, report = root / "session.json", root / "report.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        login_env = dict(env, APPLEPACKAGE_PASSWORD=password, LAB_ENROLLMENT_INPUT_PATH=str(handoff), LAB_AUTHORIZATION_PURPOSE=purpose)
        try:
            code, out, err = run_private([login_binary, "login", email], login_env, timeout=120)
        except subprocess.TimeoutExpired:
            return clean({"status": "login_timeout"})
        if code:
            ambiguous = b"apple_auth_ambiguous_bad_login" in out + err
            return clean({"status": "login_ambiguous" if ambiguous else "login_failed"})
        if not handoff.is_file() or handoff.stat().st_size > 65536 or handoff.stat().st_mode & 0o077:
            return clean({"status": "private_handoff_failed"})
        data = handoff.read_bytes()
        handoff.unlink()
        private = json.loads(data)
        allowed = {"dsid", "token", "guid"}
        if session_context in {"store", "cookies"}:
            allowed.add("cookies")
        if session_context in {"store", "storefront"}:
            allowed.add("storefront")
        data = json.dumps({key: private[key] for key in allowed if key in private}).encode()
        del private
        try:
            code, _, _ = run_private([native_binary, str(report)], env, data=data, timeout=75)
        except subprocess.TimeoutExpired:
            return clean({"status": "native_timeout"})
        finally:
            del data
        if code:
            return clean({"status": "native_process_failed"})
        if not report.is_file() or report.stat().st_size > 65536:
            return clean({"status": "private_handoff_failed"})
        result = clean(json.loads(report.read_text()))
        result["store_session_authenticated"] = True
        result["authentication_purpose"] = purpose
        result["session_context"] = session_context
        return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login-binary", required=True)
    parser.add_argument("--native-binary", required=True)
    parser.add_argument("--purpose", choices=("signIn", "machineAuthorize", "machineSession"), default="signIn")
    parser.add_argument("--session-context", choices=("token", "cookies", "storefront", "store"), default="token")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        r = trial(str(Path(args.login_binary).resolve()), str(Path(args.native_binary).resolve()), args.purpose, args.session_context)
    except Exception:
        r = clean({"status": "probe_failed"})
    print(json.dumps(r, sort_keys=True))
    # A successful import still does not establish model recovery or IPA decryption.
    return 0 if r["status"] == "keybag_imported_model_unverified" else 2

if __name__ == "__main__":
    raise SystemExit(main())
