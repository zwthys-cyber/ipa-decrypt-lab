"""Inspect public Apple Store route configuration without account credentials."""
import json
import os
import plistlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

AGENT = "Configurator/2.17 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6"
BAG_URL = "https://init.itunes.apple.com/bag.xml?guid=000000000000"
MAX_BYTES = 2 * 1024 * 1024
KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,95}$")
INTEREST = re.compile(r"account|machine|authoriz|device|summary", re.I)

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError("invalid_size")
    start, end = raw.find(b"<plist"), raw.find(b"</plist>")
    if start >= 0 and end >= start:
        raw = raw[start:end + len(b"</plist>")]
    obj = plistlib.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("invalid_plist")
    return obj

def route(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    p = urllib.parse.urlsplit(value)
    if p.scheme not in {"https", "http", "itmss", "itms"} or not p.hostname:
        return None
    if p.username or p.password or p.port not in {None, 80, 443}:
        return None
    if not (p.hostname == "apple.com" or p.hostname.endswith(".apple.com")):
        return None
    if not re.fullmatch(r"/[A-Za-z0-9_./-]*", p.path):
        return None
    # Configuration query values are not part of the public report.
    return dict(scheme=p.scheme, host=p.hostname, path=p.path,
                query_keys=sorted({k for k, _ in urllib.parse.parse_qsl(p.query)
                                   if KEY.fullmatch(k)})[:16])

def inspect(obj):
    found, interesting_keys, shapes = [], set(), []
    visited = 0
    def walk(value, depth=0):
        nonlocal visited
        if depth > 8 or visited >= 12000:
            return
        visited += 1
        if isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, str) or not KEY.fullmatch(k):
                    continue
                if INTEREST.search(k):
                    interesting_keys.add(k)
                    shape = {"key": k, "kind": type(v).__name__}
                    if isinstance(v, dict):
                        shape["child_keys"] = sorted(x for x in v if isinstance(x, str) and KEY.fullmatch(x))[:40]
                    if isinstance(v, str):
                        p = urllib.parse.urlsplit(v)
                        shape["scheme"] = p.scheme if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9+.-]{0,30}", p.scheme) else "absent"
                        shape["host"] = p.hostname if p.hostname and re.fullmatch(r"[a-zA-Z0-9.-]{1,253}", p.hostname) else "unclassified"
                        shape["path"] = p.path if re.fullmatch(r"[A-Za-z0-9_./%()-]{0,512}", p.path) else "unclassified"
                        shape["relative_path"] = bool(v.startswith("/"))
                        shape["contains_placeholder"] = "{" in v or "$" in v
                        shape["template_url"] = route(v.replace("{$pitspd-}", "").replace("{$pitspd}", ""))
                    shapes.append(shape)
                    endpoint = route(v)
                    if endpoint:
                        found.append(dict(key=k, **endpoint))
                if isinstance(v, bytes) and k in {"bag", "urlBag"}:
                    try:
                        walk(decode(v), depth + 1)
                    except (ValueError, plistlib.InvalidFileException):
                        pass
                elif isinstance(v, (dict, list)):
                    walk(v, depth + 1)
        elif isinstance(value, list):
            for item in value[:200]:
                walk(item, depth + 1)
    walk(obj)
    return dict(routes=sorted(found, key=lambda r: (r["key"], r["host"], r["path"]))[:80],
                interesting_keys=sorted(interesting_keys)[:160], shapes=shapes[:160], traversal_limit=visited >= 12000)

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("APPLE_ID") or os.environ.get("APPLE_PASSWORD"):
        raise SystemExit("Credential-free GitHub Actions required")
    report = dict(schema="ipa-lab-public-store-routes-v1", credentials_used=False,
                  account_request_attempted=False, status="fetch_failed")
    request = urllib.request.Request(BAG_URL, headers={"User-Agent": AGENT, "Accept": "application/xml"})
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            report["http_status"] = response.status
            raw = response.read(MAX_BYTES + 1)
        report.update(inspect(decode(raw)))
        report["status"] = "routes_observed"
    except urllib.error.HTTPError as error:
        report["http_status"] = error.code
        report["status"] = "redirect_blocked" if 300 <= error.code < 400 else "http_failed"
    except Exception:
        report["status"] = "fetch_or_parse_failed"
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "routes_observed" else 2

if __name__ == "__main__":
    raise SystemExit(main())
