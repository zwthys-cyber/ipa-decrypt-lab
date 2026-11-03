"""Account-authorized original IPA acquisition; GitHub Actions only."""
import argparse, json, os, re, secrets, subprocess, sys, tempfile, urllib.parse, urllib.request
from pathlib import Path
from private_trial import evaluate

def app_id(value):
    value = value.strip()
    if re.fullmatch(r"[1-9][0-9]{4,19}", value):
        return value
    u = urllib.parse.urlsplit(value)
    match = re.search(r"/id([1-9][0-9]{4,19})(?:/|$)", u.path)
    if u.scheme != "https" or u.hostname != "apps.apple.com" or u.username or not match:
        raise ValueError("invalid App Store ID or link")
    return match.group(1)

def invoke(binary, args, passphrase):
    # No shell. Never relay upstream stdout/stderr (can contain account data).
    return subprocess.run([binary, "--non-interactive", "--format", "json",
                           "--keychain-passphrase", passphrase] + args,
                          capture_output=True, text=True, timeout=420)

def login(binary, email, password, code, passphrase, run=invoke):
    args = ["auth", "login", "--email", email, "--password", password]
    if code:
        args += ["--auth-code", code]
    result = run(binary, args, passphrase)
    output = (result.stdout + result.stderr).lower()
    if "2fa code is required" in output or "auth-code" in output and "required" in output:
        return "requires_2fa"
    if result.returncode != 0:
        return "authentication_failed"
    # Upstream may return zero even when no usable session exists.
    check = run(binary, ["auth", "info"], passphrase)
    return "authenticated" if check.returncode == 0 else "session_unverified"

def metadata(identifier):
    url = "https://itunes.apple.com/lookup?" + urllib.parse.urlencode(
        {"id": identifier, "country": "us", "entity": "software"})
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(2*1024*1024 + 1)
    if len(data) > 2*1024*1024:
        raise ValueError("metadata response exceeded budget")
    results = json.loads(data).get("results", [])
    if len(results) != 1 or str(results[0].get("trackId")) != identifier:
        raise ValueError("app not found in US storefront")
    if results[0].get("price") != 0:
        raise ValueError("first version supports free apps only")
    return results[0]

def acquire(binary, engine, target, email, password, code):
    identifier = app_id(target)
    try:
        metadata(identifier)  # Enforce free current US application before license acquisition.
    except Exception:
        return {"status": "metadata_lookup_failed", "downloaded": False, "decryption_proven": False}
    passphrase = secrets.token_urlsafe(32)
    try:
        state = login(binary, email, password, code, passphrase)
    except subprocess.TimeoutExpired:
        return {"status": "authentication_timeout", "downloaded": False, "decryption_proven": False}
    except Exception:
        return {"status": "authentication_setup_failed", "downloaded": False, "decryption_proven": False}
    if state != "authenticated":
        return {"status": state, "downloaded": False, "decryption_proven": False}
    try:
        with tempfile.TemporaryDirectory(prefix="ipa-store-acquire-") as d:
            root = Path(d)
            output = root/"original.ipa"
            result = invoke(binary, ["download", "--app-id", identifier, "--platform", "iphone",
                                     "--purchase", "--output", str(output)], passphrase)
            if result.returncode or not output.is_file():
                return {"status": "download_failed", "downloaded": False, "decryption_proven": False}
            summary = evaluate(output, engine, root)
            summary["downloaded"] = True
            summary["status"] = "downloaded_and_diagnosed"
            return summary
    finally:
        try:
            invoke(binary, ["auth", "revoke"], passphrase)
        except Exception:
            pass  # Hosted runner is destroyed after job; never persist the session.

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ipatool", required=True)
    parser.add_argument("--engine", required=True)
    parser.add_argument("--target", default="6599842047")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print('{"status":"requires_github_actions"}')
        return 2
    email, password = os.environ.get("APPLE_ID", ""), os.environ.get("APPLE_PASSWORD", "")
    if not email or not password:
        print('{"status":"missing_credentials","required":["APPLE_ID","APPLE_PASSWORD"]}')
        return 2
    try:
        result = acquire(str(Path(args.ipatool).resolve()), str(Path(args.engine).resolve()),
                         args.target, email, password, os.environ.get("APPLE_2FA_CODE", ""))
    except Exception:
        # No exception strings: URLs, raw auth payloads and account info stay private.
        result = {"status": "acquisition_failed", "downloaded": False, "decryption_proven": False}
    print(json.dumps(result))
    return 0 if result.get("downloaded") else 2

if __name__ == "__main__":
    sys.exit(main())
