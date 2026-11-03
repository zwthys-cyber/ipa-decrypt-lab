"""Private, fail-closed adapter for the pinned offline IPA verifier."""
import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import subprocess
import tempfile
from ipa_audit import audit

MODEL_LIMIT = 32 * 1024

def readiness():
    value = os.environ.get("FAIRPLAY_MODEL_B64", "")
    if not value:
        return "missing_enrollment_model"
    try:
        if len(value) > 44 * 1024:
            return "invalid_enrollment_model_encoding"
        data = base64.b64decode(value, validate=True)
        if not data or len(data) > MODEL_LIMIT:
            return "invalid_enrollment_model_encoding"
    except (ValueError, binascii.Error):
        return "invalid_enrollment_model_encoding"
    return None

def outcome(status, verified=False):
    return {"status": status, "decryption_proven": verified,
            "plaintext_verified": verified, "runtime_verified": False,
            "plaintext_retained": False}

def sanitized_report(value, expected_images):
    if (not isinstance(value, dict)
            or value.get("schema") not in {"unfairplay-model-verification-v1", "unfairplay-model-verification-v2"}
            or value.get("success") is not True or value.get("plaintext_retained") is not False
            or type(value.get("encrypted_images")) is not int
            or value["encrypted_images"] != expected_images or expected_images < 1
            or type(value.get("decrypted_pages")) is not int
            or not 0 < value["decrypted_pages"] <= 1024 * 1024
            or type(value.get("plaintext_verified")) is not bool):
        return outcome("offline_invalid_report")
    verified = value["plaintext_verified"]
    result = outcome("offline_plaintext_verified" if verified else "offline_plaintext_unverified", verified)
    result.update(encrypted_images=value["encrypted_images"], decrypted_pages=value["decrypted_pages"])
    return result

def verify(binary, ipa, run=None):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return outcome("requires_github_actions")
    missing = readiness()
    if missing:
        return outcome(missing)
    run = run or subprocess.run
    try:
        info = audit(ipa)
        expected = info["encrypted_slice_count"]
        if expected < 1:
            return outcome("no_encrypted_slices_to_verify")
        # Both the raw report and any temporary plaintext stay within this private tree.
        with tempfile.TemporaryDirectory(prefix="offline-ipa-private-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            model = root/"model.bin"
            descriptor = os.open(model, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as output:
                output.write(base64.b64decode(os.environ["FAIRPLAY_MODEL_B64"], validate=True))
            env = {key: os.environ[key] for key in ("HOME", "PATH", "LANG") if key in os.environ}
            env.update(TMPDIR=str(root), TMP=str(root), TEMP=str(root))
            result = run([str(Path(binary).resolve()), "verify", "--input", str(Path(ipa).resolve()),
                          "--model", str(model)],
                         env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=180)
            if result.returncode:
                return outcome("offline_verification_rejected")
            if len(result.stdout) > 1024 * 1024:
                return outcome("offline_invalid_report")
            return sanitized_report(json.loads(result.stdout), expected)
    except subprocess.TimeoutExpired:
        return outcome("offline_verification_timeout")
    except Exception:
        # Never publish upstream errors, hashes, selectors, model contents or paths.
        return outcome("offline_verification_failed")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary")
    parser.add_argument("--ipa")
    parser.add_argument("--check-ready", action="store_true")
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        result = outcome("requires_github_actions")
    elif args.check_ready:
        result = outcome(readiness() or "model_encoding_present_unverified")
    elif not args.binary or not args.ipa:
        result = outcome("missing_input")
    else:
        result = verify(args.binary, args.ipa)
    print(json.dumps(result))
    if args.check_ready:
        return 0 if result["status"] == "model_encoding_present_unverified" else 2
    return 0 if result["plaintext_verified"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
