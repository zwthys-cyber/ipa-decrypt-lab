"""Independent Swift authentication/download trial; GitHub-hosted only."""
import argparse, json, os, subprocess, tempfile
from pathlib import Path
from store_download import app_id, metadata
from private_trial import evaluate

def classify(result):
    text = (result.stdout + result.stderr).lower()
    if "apple_auth_ambiguous_bad_login" in text:
        return "native_generic_bad_login"
    if result.returncode == 0:
        return "authenticated"
    if "verification" in text and "code" in text:
        return "native_verification_unresolved"
    if "sap" in text or "certificate" in text:
        return "native_signing_failed"
    if "429" in text:
        return "native_rate_limited"
    return "native_authentication_failed"

def classify_download(result):
    text = (result.stdout + result.stderr).lower()
    if "apple_auth_ambiguous_bad_login" in text:
        return "native_download_authentication_rejected"
    if "license" in text:
        return "native_license_failed"
    if "terms" in text:
        return "native_terms_confirmation_required"
    if "token" in text and "expired" in text:
        return "native_password_token_expired"
    if "version" in text:
        return "native_version_resolution_failed"
    if "no items" in text or "noitems" in text:
        return "native_download_no_items"
    return "native_download_failed"

def run(binary, args, env):
    return subprocess.run([binary] + args, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=300)

def trial(binary, engine, target):
    info = metadata(app_id(target))
    email = os.environ["APPLE_ID"].strip()
    env = dict(os.environ)
    env["APPLEPACKAGE_PASSWORD"] = os.environ["APPLE_PASSWORD"]
    login_args = ["login", email]
    if os.environ.get("APPLE_2FA_CODE"):
        login_args += ["--code", os.environ["APPLE_2FA_CODE"]]
    try:
        state = classify(run(binary, login_args, env))
        if state != "authenticated":
            return {"status": state, "downloaded": False, "decryption_proven": False}
        with tempfile.TemporaryDirectory(prefix="native-store-trial-") as d:
            root = Path(d)
            ipa = root/"original.ipa"
            result = run(binary, ["download", email, info["bundleId"], "--output", str(ipa)], env)
            if result.returncode or not ipa.is_file():
                return {"status": classify_download(result), "authenticated": True, "downloaded": False}
            result = evaluate(ipa, engine, root)
            result.update(status="native_downloaded_and_diagnosed", downloaded=True)
            return result
    finally:
        try:
            run(binary, ["logout", email], env)
        except Exception:
            pass

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--engine", required=True)
    p.add_argument("--target", default="6599842047")
    args = p.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print('{"status":"requires_github_actions"}')
        return 2
    if not os.environ.get("APPLE_ID") or not os.environ.get("APPLE_PASSWORD"):
        print('{"status":"missing_credentials"}')
        return 2
    try:
        result = trial(str(Path(args.binary).resolve()), str(Path(args.engine).resolve()), args.target)
    except subprocess.TimeoutExpired:
        result = {"status": "native_timeout", "downloaded": False}
    except Exception:
        result = {"status": "native_trial_failed", "downloaded": False}
    print(json.dumps(result))
    return 0 if result.get("downloaded") else 2

if __name__ == "__main__":
    raise SystemExit(main())
