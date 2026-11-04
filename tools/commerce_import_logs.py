"""Reduce a short account-free system-log window to fixed metadata only."""
from datetime import datetime, timezone
import json
import re
import subprocess
from machine_enrollment import run_private

MAX_OUTPUT = 1048576
ALLOWED_CODES = {-42023, -42032, -42018, 505, 4099}
PROCESSES = {"commerce", "fpsd"}
BAG = re.compile(r"key.?bag|diversity|divbag", re.I)
FAILURE = re.compile(r"fail|error|unable|could not|invalid|reject", re.I)

def summarize(raw, start, end):
    result = dict(status="no_matching_events", matched_events=0, import_mentions=0,
        rejection_mentions=0, known_error_codes=[], import_verified=False)
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_OUTPUT:
        result["status"] = "output_limit"
        return result
    codes = set()
    for line in raw.splitlines():
        if len(line) > 16384:
            continue
        try:
            event = json.loads(line)
            if type(event) is not dict:
                continue
            path, message, stamp = (event.get(key) for key in
                ("processImagePath", "eventMessage", "timestamp"))
            if not all(type(value) is str for value in (path, message, stamp)):
                continue
            if path.rsplit("/", 1)[-1] not in PROCESSES or len(message) > 8192:
                continue
            when = datetime.fromisoformat(stamp)
            if when.tzinfo is None or not start <= when <= end or not BAG.search(message):
                continue
        except (ValueError, TypeError, OverflowError):
            continue
        result["matched_events"] += 1
        if "import" in message.lower():
            result["import_mentions"] += 1
            if FAILURE.search(message):
                result["rejection_mentions"] += 1
                for number in re.findall(r"(?<![0-9])-?[0-9]{1,7}(?![0-9])", message):
                    code = int(number)
                    if code in ALLOWED_CODES:
                        codes.add(code)
        if result["matched_events"] >= 4096:
            result["status"] = "event_limit"
            break
    else:
        if result["matched_events"]:
            result["status"] = "window_observed"
    result["known_error_codes"] = sorted(codes)
    return result

def collect(start, end):
    base = dict(import_verified=False)
    if (not isinstance(start, datetime) or not isinstance(end, datetime)
            or start.tzinfo is None or end.tzinfo is None or end < start
            or (end - start).total_seconds() > 60):
        return dict(base, status="invalid_window")
    # log show accepts whole seconds; JSON timestamps enforce the precise interval.
    lo = start.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    hi = datetime.fromtimestamp(end.timestamp()+1, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    env = {"PATH": "/usr/bin:/bin", "TZ": "UTC"}
    argv = ["/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
        "PATH=/usr/bin:/bin", "TZ=UTC", "/usr/bin/log", "show",
        "--style", "ndjson", "--info", "--debug", "--start", lo, "--end", hi,
        "--predicate", 'process == "commerce" OR process == "fpsd"']
    try:
        code, output, _ = run_private(argv, env, timeout=15)
    except subprocess.TimeoutExpired:
        return dict(base, status="log_timeout")
    except OSError:
        return dict(base, status="log_unavailable")
    if code:
        return dict(base, status="log_unavailable")
    if len(output) > MAX_OUTPUT:
        return dict(base, status="output_limit")
    return summarize(output.decode("utf-8", errors="replace"), start, end)
