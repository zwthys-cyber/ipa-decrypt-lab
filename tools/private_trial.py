"""Manual GitHub-only IPA diagnostic. No IPA/candidate artifacts or identifying logs."""
import json, os, shutil, subprocess, sys, tempfile, urllib.parse, urllib.request, zipfile
from pathlib import Path
from ipa_audit import audit
from license_stage import prepare

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
        return evaluate(ipa, engine, root)


def engine_diagnostics(result):
    called, returned, number = False, False, None
    for line in result.stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") == "native_call" and event.get("requested_cryptid") == 2:
            called = True
        if event.get("event") == "native_return" and type(event.get("errno")) is int:
            if 0 <= event["errno"] <= 255:
                returned, number = True, event["errno"]
    if called:
        if not returned:
            category = "native_fault_or_incomplete"
        elif result.returncode:
            category = "native_rejected_or_invalid_result"
        else:
            category = "candidate_unverified"
    elif "encrypted start is not host-page aligned" in result.stderr:
        category = "unsupported_start_alignment"
    elif "requires an encrypted arm64 image with cryptid=1" in result.stderr:
        category = "unsupported_image"
    elif "native FairPlay remap symbol unavailable" in result.stderr:
        category = "symbol_unavailable"
    elif "cannot map source image" in result.stderr:
        category = "mapping_failed"
    else:
        category = "preflight_or_io_failed"
    return category, called, number

def runtime_diagnostics(engine):
    try:
        result = subprocess.run([engine, "probe"], capture_output=True, text=True, timeout=10)
        value = json.loads(result.stdout)
        if result.returncode or not isinstance(value, dict):
            return {"probe_available": False}
        return {
            "probe_available": True,
            "architecture": value.get("architecture") if value.get("architecture") in {"arm64", "x86_64"} else "other",
            "page_size": value.get("page_size") if type(value.get("page_size")) is int and 0 < value["page_size"] <= 65536 else None,
            "virtualized": value.get("virtualized") if type(value.get("virtualized")) is int and value["virtualized"] in {-1, 0, 1} else -1,
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {"probe_available": False}


def evaluate(ipa, engine, root):
    info = audit(ipa)
    extract_checked(ipa, root / "payload")
    summary = dict(status="diagnostic_only", binary_count=info["binary_count"],
                   encrypted_slice_count=info["encrypted_slice_count"], attempted=0,
                   rejected=0, unsupported=0, candidate_unverified=0,
                   decryption_proven=False, runtime_verified=False,
                   native_calls=0, rejection_reasons={}, native_errno_counts={},
                   license_staging=prepare(root / "payload", info),
                   runtime=runtime_diagnostics(engine))
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
                               capture_output=True, text=True, timeout=40)
            category, called, number = engine_diagnostics(r)
            summary["native_calls"] += int(called)
            summary["rejection_reasons"][category] = summary["rejection_reasons"].get(category, 0) + 1
            if number is not None:
                key = str(number)
                summary["native_errno_counts"][key] = summary["native_errno_counts"].get(key, 0) + 1
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
