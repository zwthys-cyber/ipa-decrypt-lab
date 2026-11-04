"""Bounded, private native-auth log collection. Never return raw log messages."""
import argparse
from collections import Counter
import json
import os
import re
import selectors
import subprocess
import sys
import time

MAX_BYTES = 8 * 1024 * 1024
MAX_EVENTS = 20000
PROCESSES = frozenset({
    "App Store", "appstoreagent", "amsaccountsd", "amsengagementd", "akd",
    "AppleIDAuthAgent", "AuthKitUIService", "StoreKitUIService",
})
DOMAINS = (
    "AMSErrorDomain", "ASDErrorDomain", "AKAuthenticationError", "AKAppleIDAuthenticationError",
    "com.apple.AuthKit.Errors", "NSURLErrorDomain", "NSCocoaErrorDomain",
    "NSOSStatusErrorDomain", "kCFErrorDomainCFNetwork", "MZErrorDomain", "SSErrorDomain",
)
CANONICAL = {value.lower(): value for value in DOMAINS}
DOMAIN_PATTERN = "(?:" + "|".join(re.escape(value) for value in DOMAINS) + ")"
ERROR_PATTERNS = (
    re.compile(r"\b(?:Error\s+)?Domain\s*=\s*(" + DOMAIN_PATTERN + r")\s+Code\s*=\s*(-?[0-9]{1,6})(?![0-9])", re.I),
    re.compile(r"\b(" + DOMAIN_PATTERN + r")\s+error\s+(-?[0-9]{1,6})(?![0-9])", re.I),
)
FAILURE = re.compile(r'\bfailureType\s*["\']?\s*[:=]\s*["\']?(-?[0-9]{1,6})(?![0-9])', re.I)
HTTP = re.compile(r"\b(?:HTTPStatusCode|HTTPStatus|statusCode|status code)\s*[:=]?\s*([1-5][0-9]{2})(?![0-9])", re.I)
CONTEXT = re.compile(r"\bauthenticat\w*|\blogin\b|\bsign[ -]?in\b|\bcredential\w*|\bpassword\w*", re.I)
SYMBOLS = (
    "MZFinance.BadLogin.Configurator_message", "MZCommerce.BadPasswordToken",
    "MZCommerce.ExpiredPasswordToken", "MZFinance.BadLogin",
)
SYMBOL_PATTERNS = {
    value: re.compile(r"(?<![A-Za-z0-9_.])" + re.escape(value) + r"(?![A-Za-z0-9_.])")
    for value in SYMBOLS
}
PREDICATE = "(" + " OR ".join('process == "' + name + '"' for name in sorted(PROCESSES)) + ")"

def capture(command, *, timeout=15, limit=MAX_BYTES):
    """Drain a child with hard time/output limits. Raw bytes stay in memory."""
    process = None
    selector = selectors.DefaultSelector()
    data = bytearray()
    state = "ok"
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LC_ALL": "C"},
        )
        selector.register(process.stdout, selectors.EVENT_READ)
        end = time.monotonic() + timeout
        while True:
            remaining = end - time.monotonic()
            if remaining <= 0:
                state = "timeout"
                break
            events = selector.select(min(remaining, 0.5))
            if not events:
                continue
            chunk = os.read(process.stdout.fileno(), min(65536, limit - len(data) + 1))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > limit:
                state = "limit_reached"
                break
        if state == "ok":
            try:
                process.wait(timeout=max(0.01, end - time.monotonic()))
            except subprocess.TimeoutExpired:
                state = "timeout"
            else:
                if process.returncode != 0:
                    state = "log_command_failed"
        return state, bytes(data) if state == "ok" else b""
    except Exception:
        return "collector_failed", b""
    finally:
        selector.close()
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if process.stdout:
                process.stdout.close()
        data.clear()

def summarize(raw):
    try:
        values = json.loads(raw)
    except (ValueError, UnicodeError, TypeError):
        return {"capture_status": "malformed_log"}
    if not isinstance(values, list) or len(values) > MAX_EVENTS:
        return {"capture_status": "event_limit_or_invalid_log"}
    counts = Counter()
    examined = 0
    oversized = 0
    for value in values:
        if not isinstance(value, dict):
            continue
        path = value.get("processImagePath")
        process = path.rsplit("/", 1)[-1] if isinstance(path, str) else value.get("process")
        if not isinstance(process, str) or process not in PROCESSES:
            continue
        message = value.get("eventMessage")
        if not isinstance(message, str):
            continue
        if len(message) > 65536:
            oversized += 1
            continue
        examined += 1
        auth = bool(CONTEXT.search(message))
        matches = set()
        for pattern in ERROR_PATTERNS:
            for match in pattern.finditer(message):
                matches.add(("error", CANONICAL[match.group(1).lower()], int(match.group(2))))
        for match in FAILURE.finditer(message):
            matches.add(("failure_type", "", int(match.group(1))))
        for match in HTTP.finditer(message):
            matches.add(("http", "", int(match.group(1))))
        for name, pattern in SYMBOL_PATTERNS.items():
            if pattern.search(message):
                matches.add(("symbol", name, 0))
        for kind, domain, code in matches:
            counts[(process, auth, kind, domain, code)] += 1
    records = [
        {"process": process, "authentication_context": auth, "kind": kind,
         "domain_or_symbol": domain, "code": code, "events": count}
        for (process, auth, kind, domain, code), count in sorted(counts.items())
    ]
    return {"capture_status": "ok", "events_examined": examined, "oversized_events_skipped": oversized,
            "record_limit_reached": len(records) > 64, "records": records[:64]}

def collect(started, *, ended=None):
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return {"capture_status": "requires_github_macos"}
    ended = int(time.time()) if ended is None else ended
    if type(started) is not int or type(ended) is not int or not 0 <= ended - started <= 300:
        return {"capture_status": "invalid_time_window"}
    state, raw = capture([
        "/usr/bin/log", "show", "--style", "json", "--info",
        "--start", "@" + str(started), "--end", "@" + str(ended), "--predicate", PREDICATE,
    ])
    if state != "ok":
        return {"capture_status": state}
    return summarize(raw)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.check:
        print('{"capture_status":"missing_check_flag"}')
        return 2
    result = collect(int(time.time()) - 2)
    # Preflight reports availability only; no pre-existing event data is exported.
    print(json.dumps({"capture_status": result["capture_status"], "decryption_proven": False}))
    return 0 if result["capture_status"] == "ok" else 2

if __name__ == "__main__":
    raise SystemExit(main())
