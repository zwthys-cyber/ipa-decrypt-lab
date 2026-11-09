"""Inspect existing CN cookie eligibility without making an Apple request."""
import json
import math
import os
from pathlib import Path
import re
import time
from cn_session import decode

def inspect(env, now=None):
    now = time.time() if now is None else now
    _, session = decode(env, now)
    cookies = session["cookies"]
    root = 0
    for item in cookies:
        if type(item) is not dict:
            continue
        # A leading dot records a domain cookie. Do not widen a host cookie.
        if item.get("domain") != ".apple.com" or item.get("path") != "/":
            continue
        name, value = item.get("name"), item.get("value")
        if (type(name) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,128}", name) is None
                or type(value) is not str or not 0 < len(value) <= 8192
                or not all(32 <= ord(c) < 127 and c != ";" for c in value)):
            continue
        expiry = item.get("expiresAt")
        if expiry is not None and (type(expiry) not in (int, float)
                or not math.isfinite(expiry) or expiry <= now):
            continue
        root += 1
    return {
        "schema": "testflight-cn-cookie-inspection-v1",
        "status": "root_cookies_require_tf_verification" if root else "mac_store_login_required",
        "saved_cn_session_valid": True,
        "saved_protocol": "configurator",
        "cookie_count": len(cookies),
        "unexpired_root_domain_cookie_count": root,
        "apple_request_attempted": False,
        "invitation_accepted": False,
        "credentials_changed": False,
        "raw_values_published": False,
    }

def main():
    os.umask(0o077)
    try:
        report = inspect(dict(os.environ))
    except Exception:
        report = {
            "schema": "testflight-cn-cookie-inspection-v1",
            "status": "saved_cn_session_invalid",
            "saved_cn_session_valid": False,
            "apple_request_attempted": False,
            "invitation_accepted": False,
            "credentials_changed": False,
            "raw_values_published": False,
        }
    encoded = json.dumps(report, sort_keys=True)
    Path("tf-cn-cookie-receipt.json").write_text(encoded)
    print(encoded, flush=True)
    return 0 if report["saved_cn_session_valid"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
