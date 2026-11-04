"""Separately confirmed, single-attempt account-wide computer deauthorization."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import store_account_summary as account

ENDPOINT = "https://buy.itunes.apple.com/account/deauthAllMachines"
CONFIRMATION = "DEAUTHORIZE ALL 5 COMPUTERS"


def base_report():
    return dict(schema="ipa-lab-store-deauthorization-v1", status="not_started",
                account_scope="all_computers", mutation_request_attempted=False,
                mutation_request_count=0, authorization_request_attempted=False,
                automatic_retry=False, enrollment_created=False, decryption_proven=False)


def preview():
    return dict(base_report(), status="preview_ready", credentials_used=False,
                network_request_attempted=False, request_method="POST",
                request_host="buy.itunes.apple.com", request_path="/account/deauthAllMachines",
                request_body_bytes=0, required_current_computer_count=5,
                postcondition_computer_count=0, maximum_mutation_requests=1,
                affects_all_computer_purchase_authorizations=True,
                apple_documented_all_deauthorization_limit="once_per_year",
                next_step_requires_explicit_confirmation=True)


def mutation_request(session, confirmation):
    if confirmation != CONFIRMATION:
        raise ValueError("explicit_confirmation_required")
    # Reuse the validated login identity, but discard the read-only query body.
    original = account.make_request(account.ENDPOINT, session)
    headers = {key: value for key, value in original.header_items() if key.lower() != "cookie"}
    target = urllib.parse.urlsplit(ENDPOINT)
    cookie = account.scoped_cookie_header(session["cookies"], target.hostname, target.path)
    if cookie:
        headers["Cookie"] = cookie
    return urllib.request.Request(ENDPOINT, data=b"", headers=headers, method="POST")


def confirmed_count(result):
    return (type(result) is dict and result.get("status") == "computer_count_observed"
            and result.get("computer_count_observed") is True
            and result.get("store_session_authenticated") is True
            and result.get("http_status") == 200
            and type(result.get("authorized_computers")) is int
            and 0 <= result["authorized_computers"] <= 5)


def operate(session, confirmation, opener=None):
    report = base_report()
    if confirmation != CONFIRMATION:
        return dict(report, status="explicit_confirmation_required")
    session = account.validate_session(session)
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), account.NoRedirect())
    try:
        before = account.fetch_summary(session, opener)
    except Exception:
        return dict(report, status="precondition_count_unavailable")
    if not confirmed_count(before):
        return dict(report, status="precondition_count_unavailable")
    report["count_before"] = before["authorized_computers"]
    if report["count_before"] != 5:
        return dict(report, status="precondition_count_changed")
    request = mutation_request(session, confirmation)
    report.update(mutation_request_attempted=True, mutation_request_count=1)
    try:
        try:
            response = opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            report["mutation_http_status"] = response.code
            report["mutation_redirect_blocked"] = 300 <= response.code <= 399
            raw = response.read(account.MAX_RESPONSE + 1)
            report["mutation_response_oversized"] = len(raw) > account.MAX_RESPONSE
            del raw
    except Exception:
        # A timeout cannot establish whether the server applied the operation.
        report["mutation_transport_failed"] = True
    # Never repeat the mutation. Re-read current state, even after a transport error.
    try:
        after = account.fetch_summary(session, opener)
    except Exception:
        return dict(report, status="postcondition_count_unavailable")
    if not confirmed_count(after):
        return dict(report, status="postcondition_count_unavailable")
    report["count_after"] = after["authorized_computers"]
    if report["count_after"] != 0:
        return dict(report, status="deauthorization_not_confirmed")
    if (report.get("mutation_http_status") == 200
            and report.get("mutation_response_oversized") is False
            and report.get("mutation_redirect_blocked") is False):
        return dict(report, status="deauthorization_confirmed")
    return dict(report, status="count_zero_after_unconfirmed_response")


def trial(login_binary, confirmation):
    report = base_report()
    if confirmation != CONFIRMATION:
        return dict(report, status="explicit_confirmation_required")
    email, password = os.environ.get("APPLE_ID"), os.environ.get("APPLE_PASSWORD")
    if not email or not password:
        return dict(report, status="missing_credentials")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-confirmed-deauthorization-") as tmp:
        handoff = Path(tmp) / "session.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true",
               "APPLEPACKAGE_PASSWORD": password, "LAB_ENROLLMENT_INPUT_PATH": str(handoff),
               "LAB_AUTHORIZATION_PURPOSE": "signIn"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        try:
            code, out, err = account.run_private([login_binary, "login", email], env, timeout=120)
        except subprocess.TimeoutExpired:
            return dict(report, status="login_timeout")
        if code:
            ambiguous = b"apple_auth_ambiguous_bad_login" in out + err
            return dict(report, status="login_ambiguous" if ambiguous else "login_failed")
        del out, err
        try:
            session = account.read_handoff(handoff)
        except Exception:
            return dict(report, status="private_handoff_failed")
        return operate(session, confirmation)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preview", "deauthorize"), default="preview")
    parser.add_argument("--login-binary")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("GitHub-hosted Actions required")
    if args.mode == "preview":
        if os.environ.get("APPLE_ID") or os.environ.get("APPLE_PASSWORD"):
            raise SystemExit("Preview must not receive account credentials")
        report = preview()
    else:
        if sys.platform != "darwin" or not args.login_binary:
            raise SystemExit("GitHub-hosted macOS login client required")
        try:
            report = trial(str(Path(args.login_binary).resolve()), os.environ.get("LAB_CONFIRMATION", ""))
        except Exception:
            report = dict(schema="ipa-lab-store-deauthorization-v1",
                          status="operation_failed_do_not_retry", operation_state_unknown=True,
                          automatic_retry=False, enrollment_created=False, decryption_proven=False)
    report["mode"] = args.mode
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in {"preview_ready", "deauthorization_confirmed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
