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

STATUSES = {"commerce_request_prepared", "commerce_import_unverified", "commerce_service_failed", "commerce_connection_changed", "invalid_diversitybag", "diversitybag_import_failed", "keybag_context_changed", "keybag_context_unavailable", "invalid_keybag_rejected", "invalid_keybag_unexpected_result", "invalid_private_input", "request_preparation_failed", "request_timeout", "request_stopped",
    "response_not_plist", "keybag_not_issued", "import_interface_unavailable",
    "keybag_imported_model_unverified", "keybag_import_failed", "native_exception", "probe_failed",
    "missing_credentials", "login_failed", "login_ambiguous", "login_timeout", "native_timeout",
    "native_process_failed", "private_handoff_failed"}
BOOLS = {"running_as_root", "diversitybag_present", "diversity_import_attempted", "diversity_import_succeeded", "diversity_error_present", "initial_import_succeeded", "initial_error_present", "keybag_import_attempted", "keybag_retry_attempted", "context_stable_after_diversity", "expected_invalid_diversity_rejected", "keybag_gzip", "keybag_binary_plist", "keybag_xml", "keybag_base64_text", "shared_directory_present", "shared_directory_writable", "shared_directory_symlink", "context_stable_after_rejection", "context_ready_before_request", "context_stable_before_import", "expected_invalid_keybag_rejected", "client_agent_bound", "client_agent_changed", "md_data_present", "md_data_valid", "amd_data_present", "amd_data_valid", "authorization_request_attempted", "ephemeral_account", "session_identity_verified", "body_token_bound",
    "redirect_blocked", "response_oversized", "error_present", "apple_failure_present",
    "dialog_present", "keybag_present", "keybag_import_succeeded", "redirect_seen",
    "redirect_query_supported", "redirect_method_post", "redirect_https", "storefront_header_present",
    "message_mentions_sign_in", "message_mentions_password", "message_mentions_verification_code", "message_mentions_computer_limit"}

COMMERCE_READY = {"commerce_connection_present", "commerce_connection_stable", "commerce_import_interface_verified",
    "session_identity_verified", "body_token_bound", "client_agent_bound", "account_dsid_verified",
    "account_token_verified", "native_guid_matches_login", "session_bound", "session_user_agent_bound",
    "session_owner_bound", "session_dsid_headers_bound", "session_token_header_bound", "native_guid_preserved",
    "sync_preserved_after_binding", "token_preserved_after_binding", "needdiv_preserved_after_binding",
    "content_length_matches", "bound_route_valid", "anisette_preserved_after_binding"}
BOOLS |= COMMERCE_READY | {"commerce_import_call_returned", "commerce_followup_sync_ready",
    "commerce_followup_needs_diversitybag", "commerce_state_changed", "commerce_transport_error_received"}

LOGIN_FLAGS = {f"login_{scope}_{suffix}" for scope in ("md", "amd") for suffix in
    ("action_present", "provision_requested", "sync_requested", "reset_requested", "data_present", "data_valid")}

def clean_login_summary(value):
    return {key: value[key] for key in LOGIN_FLAGS if type(value.get(key)) is bool} if type(value) is dict else {}

IO_OPERATIONS = {"open", "openat", "fopen", "stat", "lstat", "access", "mkdir",
    "unlink", "rename", "read", "write", "pread", "pwrite", "fsync", "fclose",
    "fread", "fwrite", "flock", "ftruncate"}

def clean_io(value):
    if (type(value) is not dict or value.get("schema") != "bounded-import-io-v1"
            or type(value.get("capped")) is not bool or type(value.get("entries")) is not list
            or len(value["entries"]) > 38):
        return None
    entries, seen = [], set()
    for entry in value["entries"]:
        if type(entry) is not dict:
            return None
        area, op = entry.get("area"), entry.get("operation")
        if (type(area) is not str or area not in {"shared_sc_info", "fpsd_sc_info"}
                or type(op) is not str or op not in IO_OPERATIONS or (area, op) in seen):
            return None
        counters = ("calls", "failures", "last_errno", "permission_failures", "missing_failures")
        if any(type(entry.get(k)) is not int or not 0 <= entry[k] <= 100000 for k in counters):
            return None
        if (not entry["calls"] or entry["failures"] > entry["calls"] or entry["last_errno"] > 256
                or entry["permission_failures"] > entry["failures"] or entry["missing_failures"] > entry["failures"]
                or (not value["capped"] and entry["permission_failures"] + entry["missing_failures"] > entry["failures"])
                or (not entry["failures"] and entry["last_errno"])):
            return None
        seen.add((area, op))
        entries.append(dict(area=area, operation=op, **{k: entry[k] for k in counters}))
    return {"schema": "bounded-import-io-v1", "capped": value["capped"], "entries": entries}

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
        "keybag_size_bucket": {"under_32", "under_256", "under_4096", "larger"},
        "md_action": {"none", "SP", "SM", "RP", "other"},
        "amd_action": {"none", "SP", "SM", "RP", "other"},
        "redirect_host_kind": {"buy", "pod_buy", "finance_app", "other"},
        "redirect_path_kind": {"authorize_exact", "authorize_slash", "legacy", "legacy_slash", "other"},
    }.items():
        if type(value.get(key)) is str and value[key] in choices:
            r[key] = value[key]
    if type(value.get("session_cookie_count")) is int and 0 <= value["session_cookie_count"] <= 128:
        r["session_cookie_count"] = value["session_cookie_count"]
    if type(value.get("approved_redirect_count")) is int and 0 <= value["approved_redirect_count"] <= 1:
        r["approved_redirect_count"] = value["approved_redirect_count"]
    for key in ("error_code", "apple_failure_code", "fairplay_status", "initial_error_code", "diversity_error_code"):
        if type(value.get(key)) is int and -999999 <= value[key] <= 999999:
            r[key] = value[key]
    for key in ("import_fairplay_status", "initial_import_fairplay_status", "diversity_import_fairplay_status"):
        if type(value.get(key)) is int and -(2**31) <= value[key] < 2**31:
            r[key] = value[key]
    if type(value.get("http_status")) is int and 100 <= value["http_status"] <= 599:
        r["http_status"] = value["http_status"]
    for key in ("error_domain", "initial_error_domain", "diversity_error_domain"):
        if type(value.get(key)) is str and value[key] in DOMAINS:
            r[key] = value[key]
    for key in ("io_trace", "initial_io_trace", "diversity_io_trace"):
        trace = clean_io(value.get(key))
        if trace is not None:
            r[key] = trace
    for key in ("state_before", "state_after"):
        if type(value.get(key)) is dict:
            r[key] = {k: value[key][k] for k in STATE_KEYS if type(value[key].get(k)) is bool}
    if r["status"] == "keybag_imported_model_unverified" and not (
        all(r.get(k) is True for k in ("authorization_request_attempted", "session_identity_verified", "body_token_bound",
                                      "keybag_present", "keybag_import_succeeded", "context_ready_before_request", "context_stable_before_import", "keybag_import_attempted"))
        and type(r.get("diversitybag_present")) is bool
        and (r["diversitybag_present"] is False or (r.get("diversity_import_attempted") is True
            and r.get("diversity_import_succeeded") is True and r.get("diversity_error_present") is False
            and r.get("context_stable_after_diversity") is True))
        and type(r.get("keybag_retry_attempted")) is bool
        and (r["keybag_retry_attempted"] is False or (r.get("diversitybag_present") is True
            and r.get("initial_import_succeeded") is False and r.get("initial_import_fairplay_status") == -42023))
        and r.get("http_status") == 200 and r.get("error_present") is False
        and r.get("apple_failure_present") is False and r.get("redirect_blocked") is False
        and r.get("response_oversized") is False):
        r["status"] = "probe_failed"
    backend = value.get("backend")
    if type(backend) is str and backend in {"ams", "commerce"}:
        r["backend"] = backend
    elif backend is not None:
        r["status"] = "probe_failed"
    if backend == "commerce":
        r["import_verified"] = False
        r["keybag_import_succeeded"] = False
        r["diversity_import_succeeded"] = False
    if r["status"] in {"commerce_request_prepared", "commerce_import_unverified"}:
        valid = (backend == "commerce" and r.get("running_as_root") is False
            and all(r.get(k) is True for k in COMMERCE_READY)
            and r.get("commerce_transport_error_received") is False and r.get("error_present") is False)
        if r["status"] == "commerce_request_prepared":
            valid &= (r.get("authorization_request_attempted") is False
                and r.get("keybag_import_attempted") is False)
        else:
            valid &= (all(r.get(k) is True for k in ("authorization_request_attempted", "keybag_present",
                "keybag_import_attempted", "commerce_import_call_returned", "commerce_followup_sync_ready"))
                and r.get("http_status") == 200 and r.get("apple_failure_present") is False
                and r.get("redirect_blocked") is False and r.get("response_oversized") is False
                and type(r.get("diversitybag_present")) is bool
                and (r["diversitybag_present"] is False or r.get("diversity_import_attempted") is True))
        if not valid:
            r["status"] = "probe_failed"
    return r

def stop_private_group(process, elevated=False):
    if type(process.pid) is not int or process.pid <= 1:
        raise ValueError("invalid private process group")
    if elevated:
        subprocess.run(["/usr/bin/sudo", "-n", "--", "/bin/kill", "-KILL", "--", f"-{process.pid}"],
            env={"PATH": "/usr/bin:/bin"}, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=5, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

def run_private(argv, env, *, data=None, timeout=120):
    p = subprocess.Popen(argv, env=env, stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(input=data, timeout=timeout)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        stop_private_group(p, elevated=argv[:2] == ["/usr/bin/sudo", "-n"])
        p.communicate(timeout=5)
        raise

def native_command(binary, report, env, user="runner", probe=False):
    if user not in {"runner", "root"}:
        raise ValueError("unsupported native execution user")
    argv = [binary] + (["--import-probe"] if probe else []) + [str(report)]
    if user == "root":
        forwarded = [f"{key}={env[key]}" for key in ("PATH", "GITHUB_ACTIONS", "HOME", "LAB_IMPORT_IO") if key in env]
        argv = ["/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i"] + forwarded + argv
    return argv

def trial(login_binary, native_binary, purpose="signIn", session_context="token", client_context="native", native_user="runner", backend="ams"):
    if native_user not in {"runner", "root"} or client_context not in {"native", "login_agent"} or purpose not in {"signIn", "machineAuthorize", "machineSession", "booleanSession"} or session_context not in {"token", "cookies", "storefront", "store"}:
        return clean({"status": "invalid_private_input"})
    if backend not in {"ams", "commerce"} or (backend == "commerce" and
            (native_user != "runner" or client_context != "login_agent" or session_context != "cookies")):
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
        if os.environ.get("LAB_IMPORT_IO") == "true":
            env["LAB_IMPORT_IO"] = "1"
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
        login_summary = clean_login_summary(private.get("login_provisioning"))
        allowed = {"dsid", "token", "guid"}
        if session_context in {"store", "cookies"}:
            allowed.add("cookies")
        if session_context in {"store", "storefront"}:
            allowed.add("storefront")
        payload = {key: private[key] for key in allowed if key in private}
        if client_context == "login_agent":
            payload["client_context"] = client_context
            payload["user_agent"] = private.get("user_agent")
        if backend == "commerce":
            payload.update(backend=backend, apple_id=email)
        data = json.dumps(payload).encode()
        del payload
        del private
        try:
            code, _, _ = run_private(native_command(native_binary, report, env, native_user), env, data=data, timeout=75)
        except subprocess.TimeoutExpired:
            return clean({"status": "native_timeout"})
        finally:
            del data
        if code:
            return clean({"status": "native_process_failed"})
        if not report.is_file() or report.stat().st_size > 65536:
            return clean({"status": "private_handoff_failed"})
        result = clean(json.loads(report.read_text()))
        result["native_user"] = native_user
        if native_user == "root" and result.get("running_as_root") is not True:
            result["status"] = "probe_failed"
        result.update(login_summary)
        result["store_session_authenticated"] = True
        result["authentication_purpose"] = purpose
        result["session_context"] = session_context
        result["client_context"] = client_context
        if client_context == "login_agent" and result.get("authorization_request_attempted") is True and result.get("client_agent_bound") is not True:
            result["status"] = "probe_failed"
        return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--login-binary", required=True)
    parser.add_argument("--native-binary", required=True)
    parser.add_argument("--backend", choices=("ams", "commerce"), default="ams")
    parser.add_argument("--native-user", choices=("runner", "root"), default="runner")
    parser.add_argument("--purpose", choices=("signIn", "machineAuthorize", "machineSession", "booleanSession"), default="signIn")
    parser.add_argument("--session-context", choices=("token", "cookies", "storefront", "store"), default="cookies")
    parser.add_argument("--client-context", choices=("native", "login_agent"), default="login_agent")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        raise SystemExit("GitHub-hosted macOS required")
    try:
        r = trial(str(Path(args.login_binary).resolve()), str(Path(args.native_binary).resolve()), args.purpose, args.session_context, args.client_context, args.native_user, args.backend)
    except Exception:
        r = clean({"status": "probe_failed"})
    print(json.dumps(r, sort_keys=True))
    # A successful import still does not establish model recovery or IPA decryption.
    return 0 if r["status"] == "keybag_imported_model_unverified" else 2

if __name__ == "__main__":
    raise SystemExit(main())
