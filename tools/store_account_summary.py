"""Read only the authorized-computer count using an ephemeral Store session."""
import argparse
import json
import math
import os
from pathlib import Path
import plistlib
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

from machine_enrollment import run_private

ENDPOINT = "https://buy.itunes.apple.com/account/v1/summary/graphql"
QUERY = "query requestAccountSummary { authorizations { authorizedComputers } }"
BODY = json.dumps({"query": QUERY}, separators=(",", ":")).encode("utf-8")
MAX_RESPONSE = 1024 * 1024
UA = "Configurator/2.17 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def base_report(authenticated=False):
    return dict(schema="ipa-lab-store-account-summary-v1",
                status="query_failed", store_session_authenticated=authenticated,
                summary_request_attempted=False, approved_redirect_count=0,
                computer_count_observed=False, machine_authorization_attempted=False,
                deauthorization_attempted=False, enrollment_created=False,
                decryption_proven=False)


def safe_header(value, maximum):
    return (type(value) is str and 0 < len(value) <= maximum
            and all(32 <= ord(ch) < 127 for ch in value))


def validate_session(value):
    if type(value) is not dict:
        raise ValueError("invalid_session")
    if (type(value.get("dsid")) is not str or not re.fullmatch(r"[0-9]{1,32}", value["dsid"])
            or type(value.get("guid")) is not str or not re.fullmatch(r"[A-F0-9]{12}", value["guid"])
            or not safe_header(value.get("token"), 8192)
            or not safe_header(value.get("user_agent"), 1024)
            or not safe_header(value.get("storefront"), 256)
            or type(value.get("cookies")) is not list or len(value["cookies"]) > 128):
        raise ValueError("invalid_session")
    return {key: value[key] for key in ("dsid", "guid", "token", "user_agent", "storefront", "cookies")}


def valid_endpoint(url):
    if type(url) is not str or not url.isascii():
        return False
    parsed = urllib.parse.urlsplit(url)
    return (parsed.scheme == "https" and parsed.netloc == parsed.hostname
            and parsed.username is None and parsed.password is None
            and parsed.hostname is not None
            and re.fullmatch(r"(?:buy|p[0-9]{1,3}-buy)[.]itunes[.]apple[.]com", parsed.hostname) is not None
            and parsed.path == "/account/v1/summary/graphql"
            and not parsed.query and not parsed.fragment)


def cookie_header(cookies, url, now=None):
    if not valid_endpoint(url):
        raise ValueError("unapproved_endpoint")
    parsed = urllib.parse.urlsplit(url)
    now = time.time() if now is None else now
    items = []
    for item in cookies:
        if type(item) is not dict:
            continue
        name, value, domain, path = (item.get(key) for key in ("name", "value", "domain", "path"))
        if (type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name)
                or not safe_header(value, 8192) or ";" in value
                or type(domain) is not str or type(path) is not str or not path.startswith("/")):
            continue
        domain = domain.lower().lstrip(".")
        if not domain or not (domain == "apple.com" or domain.endswith(".apple.com")):
            continue
        if parsed.hostname != domain and not parsed.hostname.endswith("." + domain):
            continue
        if parsed.path != path and not (parsed.path.startswith(path)
                and (path.endswith("/") or parsed.path[len(path):].startswith("/"))):
            continue
        expires = item.get("expiresAt")
        if expires is not None and (type(expires) not in (int, float)
                or not math.isfinite(expires) or expires <= now):
            continue
        items.append((len(path), name + "=" + value))
    result = "; ".join(item for _, item in sorted(items, key=lambda pair: -pair[0]))
    if len(result) > 16384:
        raise ValueError("cookie_header_too_large")
    return result


def make_request(url, session=None):
    if not valid_endpoint(url):
        raise ValueError("unapproved_endpoint")
    headers = {"Content-Type": "application/json; charset=UTF-8", "Accept": "application/json",
               "Accept-Encoding": "identity", "User-Agent": UA}
    if session is not None:
        session = validate_session(session)
        headers.update({"User-Agent": session["user_agent"], "X-Dsid": session["dsid"],
                        "iCloud-DSID": session["dsid"], "X-Token": session["token"],
                        "X-Apple-Store-Front": session["storefront"]})
        cookies = cookie_header(session["cookies"], url)
        if cookies:
            headers["Cookie"] = cookies
    return urllib.request.Request(url, data=BODY, headers=headers, method="POST")


def count_type(value):
    return {int: "integer", bool: "boolean", str: "string", type(None): "null",
            dict: "object", list: "array", float: "number"}.get(type(value), "other")


def parse_response(raw, http_status, authenticated):
    report = {}
    try:
        value = json.loads(raw)
        report["response_format"] = "json"
    except (ValueError, UnicodeDecodeError):
        try:
            value = plistlib.loads(raw)
            report["response_format"] = "plist"
        except Exception:
            return dict(status="response_not_structured", response_format="other")
    if type(value) is not dict:
        return dict(status="response_shape_unexpected", **report)
    if "failureType" in value:
        code = value["failureType"]
        if type(code) is str and re.fullmatch(r"-?[0-9]{1,6}", code):
            code = int(code)
        if type(code) is int and -999999 <= code <= 999999:
            report["apple_failure_code"] = code
        return dict(status="apple_request_refused", **report)
    errors = value.get("errors")
    if errors:
        report["graphql_errors_present"] = True
        if type(errors) is list:
            report["graphql_error_count"] = min(len(errors), 100)
            messages = " ".join(item.get("message", "")[:2048] for item in errors[:20]
                                if type(item) is dict and type(item.get("message")) is str).lower()
            report["error_mentions_authentication"] = any(
                word in messages for word in ("unauthorized", "unauthenticated", "authentication", "sign in"))
            report["error_mentions_unknown_field"] = "cannot query field" in messages
        return dict(status="graphql_errors", **report)
    if http_status != 200:
        return dict(status="http_refused", **report)
    data = value.get("data")
    authorizations = data.get("authorizations") if type(data) is dict else None
    count = authorizations.get("authorizedComputers") if type(authorizations) is dict else None
    report["computer_count_field_type"] = count_type(count)
    if type(count) is not int or not 0 <= count <= 5:
        return dict(status="computer_count_not_returned", **report)
    if not authenticated:
        return dict(status="unexpected_unauthenticated_count", **report)
    return dict(status="computer_count_observed", authorized_computers=count,
                computer_count_observed=True, **report)


def fetch_summary(session=None, opener=None):
    report = base_report(session is not None)
    if session is not None:
        session = validate_session(session)
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    url = ENDPOINT
    for attempt in range(2):
        request = make_request(url, session)
        report["summary_request_attempted"] = True
        if session:
            report["session_cookie_header_present"] = request.has_header("Cookie")
            report["login_user_agent_preserved"] = request.get_header("User-agent") == session["user_agent"]
        try:
            try:
                response = opener.open(request, timeout=20)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.code
                report["http_status"] = status
                if 300 <= status <= 399:
                    location = response.headers.get("Location", "")
                    target = urllib.parse.urljoin(url, location)
                    if (attempt != 0 or status not in (307, 308)
                            or not valid_endpoint(target) or target == url):
                        return dict(report, status="redirect_blocked")
                    url = target
                    report["approved_redirect_count"] = 1
                    continue
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    return dict(report, status="response_oversized")
                report.update(parse_response(raw, status, session is not None))
                return report
        except (OSError, TimeoutError, urllib.error.URLError):
            return dict(report, status="transport_failed")
    return report


def read_handoff(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_size > 65536
                or info.st_mode & 0o077 or info.st_uid != os.getuid()):
            raise ValueError("private_handoff_failed")
        with os.fdopen(fd, "rb") as handle:
            fd = None
            raw = handle.read(65537)
        if len(raw) > 65536:
            raise ValueError("private_handoff_failed")
        return validate_session(json.loads(raw))
    finally:
        if fd is not None:
            os.close(fd)
        path.unlink(missing_ok=True)


def trial(login_binary):
    email, password = os.environ.get("APPLE_ID"), os.environ.get("APPLE_PASSWORD")
    report = base_report()
    if not email or not password:
        return dict(report, status="missing_credentials")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-readonly-account-") as tmp:
        handoff = Path(tmp) / "session.json"
        env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true",
               "APPLEPACKAGE_PASSWORD": password, "LAB_ENROLLMENT_INPUT_PATH": str(handoff),
               "LAB_AUTHORIZATION_PURPOSE": "signIn"}
        if os.environ.get("HOME"):
            env["HOME"] = os.environ["HOME"]
        try:
            code, out, err = run_private([login_binary, "login", email], env, timeout=120)
        except subprocess.TimeoutExpired:
            return dict(report, status="login_timeout")
        if code:
            ambiguous = b"apple_auth_ambiguous_bad_login" in out + err
            return dict(report, status="login_ambiguous" if ambiguous else "login_failed")
        del out, err
        try:
            session = read_handoff(handoff)
        except Exception:
            return dict(report, status="private_handoff_failed")
        return fetch_summary(session)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "query"), default="preflight")
    parser.add_argument("--login-binary")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("GitHub-hosted Actions required")
    if args.mode == "preflight" and (os.environ.get("APPLE_ID") or os.environ.get("APPLE_PASSWORD")):
        raise SystemExit("Preflight must not receive credentials")
    if args.mode == "query" and (sys.platform != "darwin" or not args.login_binary):
        raise SystemExit("GitHub-hosted macOS login client required")
    try:
        report = (fetch_summary() if args.mode == "preflight"
                  else trial(str(Path(args.login_binary).resolve())))
    except Exception:
        report = base_report()
    report["mode"] = args.mode
    print(json.dumps(report, sort_keys=True))
    if args.mode == "preflight":
        return 0 if report["status"] in {
            "apple_request_refused", "graphql_errors", "http_refused",
            "computer_count_not_returned", "response_not_structured", "redirect_blocked"
        } and report.get("http_status") in {200, 301, 302, 303, 307, 308, 400, 401, 403} else 2
    return 0 if report["status"] == "computer_count_observed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
