"""Inspect the public account-settings frontend advertised by Apple's bag."""
from collections import deque
from html.parser import HTMLParser
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from public_store_routes import AGENT, BAG_URL, NoRedirect, decode

MAX_FILE = 3 * 1024 * 1024
MAX_TOTAL = 12 * 1024 * 1024
MAX_ASSETS = 12
INTEREST = re.compile(r"DeauthAllMachines|deauthAllMachines|deauthorize|deauthorise|AuthorizationList", re.I)

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept-Encoding": "identity"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
        data = response.read(MAX_FILE + 1)
        if len(data) > MAX_FILE:
            raise ValueError("file_limit")
        return data, response.headers.get_content_type()

def safe_asset(url, root):
    p, base = urllib.parse.urlsplit(url), urllib.parse.urlsplit(root)
    prefix = base.path.rsplit("/account/settings", 1)[0] + "/"
    return (p.scheme == "https" and p.hostname == "apps.mzstatic.com"
            and p.port in {None, 443} and not p.username and not p.password and not p.query and not p.fragment
            and p.path.startswith(prefix) and ".." not in p.path
            and re.fullmatch(r"/[A-Za-z0-9_./%-]+", p.path) is not None
            and p.path.endswith((".js", ".mjs", ".json")))

class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("src"):
            self.urls.append(attrs["src"])
        if tag == "link" and attrs.get("href") and (
            attrs.get("rel") == "modulepreload" or attrs.get("as") == "script"
        ):
            self.urls.append(attrs["href"])

def inspect_text(raw):
    text = raw.decode("utf-8", "replace")
    urls = set()
    for match in re.finditer(r'https://[a-zA-Z0-9.-]+/[a-zA-Z0-9_./%-]*', text):
        p = urllib.parse.urlsplit(match[0])
        if p.hostname and (p.hostname.endswith(".apple.com") or p.hostname.endswith(".itunes.com")):
            urls.add(urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", "")))
    contexts = []
    for match in INTEREST.finditer(text):
        if len(contexts) >= 24:
            break
        fragment = text[max(0, match.start()-250):min(len(text), match.end()+700)]
        fragment = " ".join(fragment.split())
        if fragment not in contexts:
            contexts.append(fragment)
    refs = []
    patterns = (
        r'\b(?:import|export)\s*(?:[^;"\']{0,180}?\s+from\s*)?["\']([^"\']+\.(?:js|mjs))["\']',
        r'\bimport\s*\(\s*["\']([^"\']+\.(?:js|mjs))["\']\s*\)',
        r'["\']((?:\./)?assets/[A-Za-z0-9_./-]+\.(?:js|mjs))["\']',
    )
    for pattern in patterns:
        refs.extend(re.findall(pattern, text))
    modules = {}
    for module_id in (37689,):
        marker = re.search(r"(?<![0-9])" + str(module_id) + r":(?:\(|function)", text)
        if marker:
            tail = text[marker.start():marker.start()+18000]
            following = re.search(r"},[0-9]{2,6}:(?:\(|function)", tail[20:])
            modules[str(module_id)] = tail[:20+following.start()+1] if following else tail
    for match in re.finditer(r"DeauthAllMachines", text):
        headers = list(re.finditer(r"(?<![0-9])([0-9]{2,6}):(?:\(|function)", text[:match.start()]))
        if headers:
            marker = headers[-1]
            modules["origin-" + marker[1]] = text[marker.start():marker.start()+600]
    runtime_match = re.search(r"\.u\s*=\s*", text)
    runtime = []
    if runtime_match:
        loader = text[runtime_match.start():runtime_match.start()+100000]
        for chunk in (24589, 53332, 47549, 21625, 21193, 49698):
            values = re.findall(r"(?<![0-9])" + str(chunk) + r':"([^"]+)"', loader)
            names = [value for value in values if re.fullmatch(r"account-[A-Za-z0-9-]+", value)]
            hashes = [value for value in values if re.fullmatch(r"[a-f0-9]{8}", value)]
            if names and hashes:
                asset = "./" + names[0] + "." + hashes[0] + ".js"
                runtime.append(asset)
                refs.append(asset)
    return dict(known_api_urls=sorted(urls)[:40], static_code_contexts=contexts, request_modules=modules, runtime_loader=runtime), refs

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("APPLE_ID") or os.environ.get("APPLE_PASSWORD"):
        raise SystemExit("Credential-free GitHub Actions required")
    report = dict(schema="ipa-lab-public-account-frontend-v1", credentials_used=False,
                  authenticated_request_attempted=False, status="fetch_failed", assets=[])
    try:
        bag, _ = fetch(BAG_URL)
        obj = decode(bag)
        entry = obj.get("accountSummary") or obj.get("urlBag", {}).get("accountSummary")
        if not isinstance(entry, str) or not re.fullmatch(
            r"https://apps[.]mzstatic[.]com/content/[a-f0-9]{24,64}/account/settings", entry
        ):
            raise ValueError("unreviewed_entry")
        page, mime = fetch(entry)
        parser = Assets()
        parser.feed(page.decode("utf-8", "replace"))
        page_summary, refs = inspect_text(page)
        report.update(entry_host="apps.mzstatic.com", entry_mime=mime, page_bytes=len(page),
                      page=page_summary, discovered_scripts=len(parser.urls))
        candidates = [urllib.parse.urljoin(entry, url) for url in parser.urls + refs]
        candidates.sort(key=lambda url: ("vendor." in url, "apple-media-services" not in url))
        report["entry_scripts"] = [urllib.parse.urlsplit(url).path for url in candidates if safe_asset(url, entry)][:40]
        queued = deque(candidates)
        seen, total = set(), len(page)
        while queued and len(seen) < MAX_ASSETS and total < MAX_TOTAL:
            url = queued.popleft()
            if url in seen or not safe_asset(url, entry) or ("vendor." in url and "apple-media-services" not in url):
                continue
            seen.add(url)
            data, mime = fetch(url)
            total += len(data)
            if total > MAX_TOTAL:
                report["status"] = "total_limit"
                break
            summary, refs = inspect_text(data)
            report["assets"].append(dict(path=urllib.parse.urlsplit(url).path, mime=mime, bytes=len(data), **summary))
            queued.extend(urllib.parse.urljoin(url, ref) for ref in refs)
        else:
            report["status"] = "frontend_observed"
        report["total_bytes"] = total
        report["asset_limit_reached"] = len(seen) >= MAX_ASSETS
    except urllib.error.HTTPError as error:
        report.update(status="http_failed", http_status=error.code)
    except Exception:
        report["status"] = "fetch_or_parse_failed"
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "frontend_observed" else 2

if __name__ == "__main__":
    raise SystemExit(main())
