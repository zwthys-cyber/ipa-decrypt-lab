"""Manual GitHub-only IPA diagnostic. No IPA/candidate artifacts or identifying logs."""
import json, os, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path
from ipa_audit import audit

def check_url(url):
    p = urllib.parse.urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise ValueError("requires HTTPS without embedded login")
    if p.hostname.lower() in {"apps.apple.com", "itunes.apple.com"}:
        raise ValueError("store page is not an IPA download")

class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def extract_checked(ipa, root):
    with zipfile.ZipFile(ipa) as z:
        entries = z.infolist()
        if len(entries) > 4096 or sum(e.file_size for e in entries) > 1024**3:
            raise ValueError("extraction budget exceeded")
        seen = set()
        for e in entries:
            n = e.filename
            if (not n or n.startswith("/") or "\\" in n or
                any(p in {"", ".", ".."} for p in n.rstrip("/").split("/")) or n in seen or
                (e.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("unsafe archive entry")
            seen.add(n)
        for e in entries:
            dest = root.joinpath(*e.filename.rstrip("/").split("/"))
            if e.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(e) as source, open(dest, "xb") as target:
                    shutil.copyfileobj(source, target, 1024*1024)
                dest.chmod(0o600)

def trial(engine, url):
    check_url(url)
    with tempfile.TemporaryDirectory(prefix="ipa-private-trial-") as d:
        root = Path(d)
        ipa = root / "input.ipa"
        request = urllib.request.Request(url, headers={"User-Agent": "ipa-decrypt-lab/0.1"})
        opener = urllib.request.build_opener(HTTPSRedirect())
        with opener.open(request, timeout=30) as response, open(ipa, "xb") as out:
            total = 0
            while True:
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > 512*1024*1024:
                    raise ValueError("download budget exceeded")
                out.write(chunk)
        info = audit(ipa)
        extract_checked(ipa, root / "payload")
        summary = dict(status="diagnostic_only", binary_count=info["binary_count"],
                       encrypted_slice_count=info["encrypted_slice_count"], attempted=0,
                       rejected=0, unsupported=0, candidate_unverified=0,
                       decryption_proven=False, runtime_verified=False)
        for i, b in enumerate(info["binaries"]):
            encrypted = [s for s in b["slices"] if s["encryption"] and s["encryption"]["cryptid"]]
            if not encrypted:
                continue
            if len(b["slices"]) != 1 or "fat_offset" in b["slices"][0] or encrypted[0]["cpu_type"] != 0x0100000C:
                summary["unsupported"] += 1
                continue
            summary["attempted"] += 1
            output = root / ("candidate-" + str(i))
            try:
                r = subprocess.run([engine, "attempt", str(root/"payload"/b["path"]), str(output)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=40)
                key = "candidate_unverified" if r.returncode == 0 and output.is_file() else "rejected"
                summary[key] += 1
            except subprocess.TimeoutExpired:
                summary["rejected"] += 1
            finally:
                output.unlink(missing_ok=True)
        return summary

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print('{"status":"requires_github_actions"}')
        return 2
    url = os.environ.get("AUTHORIZED_IPA_URL", "")
    if not url:
        print('{"status":"missing_secret","required":"AUTHORIZED_IPA_URL"}')
        return 2
    try:
        result = trial(str(Path(sys.argv[1]).resolve()), url)
    except Exception:
        print('{"status":"trial_failed","details":"withheld_to_protect_input_metadata"}')
        return 2
    print(json.dumps(result))
    return 0

if __name__ == "__main__":
    sys.exit(main())
