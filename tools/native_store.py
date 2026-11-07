"""Independent Swift authentication/download trial; GitHub-hosted only."""
import argparse, json, os, re, subprocess, tempfile, time
from pathlib import Path
from store_download import app_id, metadata
from private_trial import evaluate
from offline_verify import verify as verify_offline, readiness as offline_readiness, outcome as offline_outcome


# Retry only explicit temporary service/transport failures. Account challenges,
# throttling, unknown failures and credential rejection must stop immediately.
AUTH_RETRYABLE = {"native_auth_service_unavailable", "native_auth_transport_failed"}
AUTH_DELAYS = (5, 10)

def authentication_diagnostics(result):
    raw = (result.stdout or "") + "\n" + (result.stderr or "")
    codes = re.findall(r"\bHTTP\s+([1-5][0-9]{2})(?![0-9])|\brequest failed with status ([1-5][0-9]{2})(?![0-9])", raw)
    http = [int(a or b) for a, b in codes][-8:]
    lower = raw.lower()
    transport = next((label for label, terms in (
        ("timeout", ("readtimeout", "connecttimeout", "timed out", "ipa_auth_timeout")),
        ("connection_reset", ("connection reset by peer", "connectionreset")),
        ("connection_closed", ("remoteconnectionclosed",)),
        ("dns", ("dns resolution failed", "nodename nor servname provided")),
    ) if any(term in lower for term in terms)), "")
    # Never return free-form stderr, response bodies, paths, URLs or account data.
    return {"exit_code": result.returncode, "http_statuses": http, "transport": transport}

def authenticate(binary, args, env, *, execute=None, on_retry=None):
    execute = execute or run
    for attempt in range(1, 4):
        try:
            result = execute(binary, args, env, timeout=45)
        except subprocess.TimeoutExpired:
            result = subprocess.CompletedProcess([], 124, "", "ipa_auth_timeout")
        state = classify(result)
        retry = state in AUTH_RETRYABLE and attempt <= len(AUTH_DELAYS)
        print(json.dumps({"schema": "ipa-auth-v1", "attempt": attempt,
                          "status": state, "retrying": retry,
                          **authentication_diagnostics(result)}), flush=True)
        if not retry:
            return result
        if on_retry is not None:
            on_retry()
        time.sleep(AUTH_DELAYS[attempt - 1])

def classify(result):
    text = ((result.stdout or "") + (result.stderr or "")).lower()
    if "apple_auth_ambiguous_bad_login" in text:
        return "native_generic_bad_login"
    if result.returncode == 0:
        return "authenticated"
    if "verification" in text and "code" in text:
        return "native_verification_unresolved"
    diagnostic = authentication_diagnostics(result)
    if diagnostic["http_statuses"]:
        last = diagnostic["http_statuses"][-1]
        if last in (401, 403):
            return "native_auth_access_denied"
        if last == 429:
            return "native_rate_limited"
        if last in (502, 503, 504):
            return "native_auth_service_unavailable"
        # Do not retry other explicit HTTP rejections, even if body text
        # incidentally contains a transport keyword.
    elif diagnostic["transport"]:
        return "native_auth_transport_failed"
    if "sap" in text or "certificate" in text:
        return "native_signing_failed"
    if "429" in text:
        return "native_rate_limited"
    return "native_authentication_failed"

def classify_download(result):
    text = "\n".join(line for line in (result.stdout + result.stderr).splitlines()
                     if not line.startswith("IPA_LAB_")).lower()
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

DOWNLOAD_STAGES = {
    "validate_output", "load_account", "resolve_country", "lookup_app",
    "resolve_version", "request_product", "acquire_free_license",
    "inspect_download", "download_bytes", "inject_signature",
    "validate_platform", "publish_file", "parse_product", "validate_product",
    "resolve_ent_endpoint", "generate_kbsync", "request_ent_product", "validate_ent_product",
}

def download_diagnostics(result):
    stages = [line.removeprefix("IPA_LAB_STAGE:") for line in result.stdout.splitlines()
              if line.startswith("IPA_LAB_STAGE:")]
    stages = [stage for stage in stages if stage in DOWNLOAD_STAGES]
    codes = [line.removeprefix("IPA_LAB_FAILURE:") for line in result.stdout.splitlines()
             if line.startswith("IPA_LAB_FAILURE:")]
    codes = [int(code) for code in codes if code.isascii() and code.isdigit() and len(code) <= 5]
    diagnostic = {"stage": stages[-1] if stages else "before_download",
                  "exit_code": result.returncode}
    if not codes:
        codes = [int(code) for code in re.findall(r"failureType:\s*([0-9]{1,5})(?![0-9])",
                                                result.stderr)]
    if codes:
        diagnostic["apple_failure_code"] = codes[-1]
    http_codes = [line.removeprefix("IPA_LAB_HTTP:") for line in result.stdout.splitlines()
                  if line.startswith("IPA_LAB_HTTP:")]
    http_codes = [int(code) for code in http_codes if code.isascii() and code.isdigit()
                  and len(code) == 3 and 100 <= int(code) <= 599]
    if http_codes:
        diagnostic["http_statuses"] = http_codes[-8:]
    if "IPA_LAB_LICENSE:unconfirmed_5002" in result.stdout.splitlines():
        diagnostic["purchase_5002_unconfirmed"] = True
    return diagnostic

def run(binary, args, env, timeout=300):
    return subprocess.run([binary] + args, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)

def trial(binary, engine, target, offline_binary=None):
    if offline_binary:
        missing = offline_readiness()
        if missing:
            return dict(offline_outcome(missing), downloaded=False)
    info = metadata(app_id(target))
    email = os.environ["APPLE_ID"].strip()
    env = dict(os.environ)
    env.pop("FAIRPLAY_MODEL_B64", None)
    env["APPLEPACKAGE_PASSWORD"] = os.environ["APPLE_PASSWORD"]
    login_args = ["login", email]
    if os.environ.get("APPLE_2FA_CODE"):
        login_args += ["--code", os.environ["APPLE_2FA_CODE"]]
    try:
        state = classify(authenticate(binary, login_args, env))
        if state != "authenticated":
            return {"status": state, "downloaded": False, "decryption_proven": False}
        with tempfile.TemporaryDirectory(prefix="native-store-trial-") as d:
            root = Path(d)
            ipa = root/"original.ipa"
            result = run(binary, ["download", email, info["bundleId"], "--output", str(ipa)], env)
            if result.returncode or not ipa.is_file():
                return {"status": classify_download(result), "authenticated": True, "downloaded": False, **download_diagnostics(result)}
            if offline_binary:
                result = verify_offline(offline_binary, ipa)
                result.update(downloaded=True, authenticated=True)
                return result
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
    p.add_argument("--offline-binary", default=os.environ.get("LAB_OFFLINE_ENGINE") or None)
    args = p.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print('{"status":"requires_github_actions"}')
        return 2
    if not os.environ.get("APPLE_ID") or not os.environ.get("APPLE_PASSWORD"):
        print('{"status":"missing_credentials"}')
        return 2
    try:
        result = trial(str(Path(args.binary).resolve()), str(Path(args.engine).resolve()), args.target, args.offline_binary)
    except subprocess.TimeoutExpired:
        result = {"status": "native_timeout", "downloaded": False}
    except Exception:
        result = {"status": "native_trial_failed", "downloaded": False}
    print(json.dumps(result))
    if args.offline_binary:
        return 0 if result.get("plaintext_verified") is True else 2
    return 0 if result.get("downloaded") else 2

if __name__ == "__main__":
    raise SystemExit(main())
