"""GitHub-only, account-free Anisette prerequisite experiment; never export headers."""
import base64
import io
import json
import logging
import os
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit

MAX_APK = 300 * 1024 * 1024
MAX_RESPONSE = 2 * 1024 * 1024
REQUIRED = ("X-Apple-I-MD", "X-Apple-I-MD-M", "X-Apple-I-MD-LU",
            "X-Apple-I-MD-RINFO", "X-Mme-Device-Id")
FLAGS = {"independent_anisette_provisioned", "required_headers_present",
         "saved_state_reusable", "machine_id_stable_after_reload"}
STATUSES = {"complete", "dependencies_unavailable", "library_initialization_failed",
            "provisioning_failed", "headers_invalid", "session_restore_failed",
            "network_policy_rejected", "network_request_limit", "network_response_limit",
            "tls_failed", "request_failed", "worker_failed", "worker_timeout",
            "invalid_apk", "requires_github_actions"}

class ProbeFailure(Exception):
    pass

def allowed_url(url):
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        return (parts.scheme == "https" and parts.port in (None, 443) and
                parts.username is None and parts.password is None and
                (host == "apple.com" or host.endswith(".apple.com") or
                 host == "mzstatic.com" or host.endswith(".mzstatic.com")))
    except (TypeError, ValueError):
        return False

def install_private_transport():
    """Constrain the pinned provider to Apple TLS endpoints; never send account secrets."""
    import urllib3
    original = urllib3.PoolManager.request
    counts = {"requests": 0}
    def request(pool, method, url, **kwargs):
        if not allowed_url(url) or method not in {"GET", "POST"}:
            raise ProbeFailure("network_policy_rejected")
        counts["requests"] += 1
        if counts["requests"] > 8:
            raise ProbeFailure("network_request_limit")
        kwargs.update(timeout=urllib3.Timeout(connect=5, read=15, total=20),
                      retries=False, redirect=False, preload_content=False)
        response = original(pool, method, url, **kwargs)
        try:
            if response.status != 200:
                raise ProbeFailure("request_failed")
            data = response.read(MAX_RESPONSE + 1)
            if len(data) > MAX_RESPONSE:
                raise ProbeFailure("network_response_limit")
            return SimpleNamespace(data=data)
        finally:
            response.close()
            response.release_conn()
    urllib3.PoolManager.request = request
    return counts

def headers_valid(value):
    if not isinstance(value, dict):
        return False
    if any(type(value.get(key)) is not str or not 0 < len(value[key]) <= 8192 for key in REQUIRED):
        return False
    try:
        if any(not base64.b64decode(value[key], validate=True) for key in REQUIRED[:3]):
            return False
    except (ValueError, TypeError):
        return False
    return value["X-Apple-I-MD-RINFO"].isdigit()

def clean(value):
    result = {"schema": "ipa-lab-anisette-prerequisite-v1", "status": "worker_failed",
              "apple_login_attempted": False, "native_state_imported": False,
              "enrollment_created": False, "decryption_proven": False}
    if not isinstance(value, dict):
        return result
    status = value.get("status")
    if isinstance(status, str) and status in STATUSES:
        result["status"] = status
    for key in FLAGS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    count = value.get("apple_requests")
    if type(count) is int and 0 <= count <= 8:
        result["apple_requests"] = count
    if result["status"] == "complete" and not all(result.get(key) is True for key in FLAGS):
        result["status"] = "worker_failed"
    return result

def worker(apk, report_path):
    result = {"status": "dependencies_unavailable"}
    logging.disable(logging.CRITICAL)
    counts = {}
    try:
        from anisette import Anisette
        counts = install_private_transport()
        result["status"] = "library_initialization_failed"
        provider = Anisette.init(str(apk))
        # Explicit local APK avoids the upstream third-party library endpoint.
        result["status"] = "provisioning_failed"
        provider.provision()
        result["independent_anisette_provisioned"] = provider.is_provisioned is True
        headers = provider.get_data()
        result["required_headers_present"] = headers_valid(headers)
        if not result["independent_anisette_provisioned"] or not result["required_headers_present"]:
            raise ProbeFailure("headers_invalid")
        result["status"] = "session_restore_failed"
        state = io.BytesIO()
        provider.save_all(state)
        state.seek(0)
        restored = Anisette.load(state)
        result["saved_state_reusable"] = restored.is_provisioned is True
        if not result["saved_state_reusable"]:
            raise ProbeFailure("session_restore_failed")
        restored_headers = restored.get_data()
        result["machine_id_stable_after_reload"] = (
            headers_valid(restored_headers) and headers["X-Apple-I-MD-M"] == restored_headers["X-Apple-I-MD-M"]
        )
        result["status"] = "complete"
        # No header, device identity, virtual filesystem, or ADI blob is exported.
        state.close()
    except ProbeFailure as error:
        result["status"] = error.args[0] if error.args else "worker_failed"
    except ssl.SSLError:
        result["status"] = "tls_failed"
    except Exception:
        # The stage identifies the failure without leaking exception text.
        pass
    result["apple_requests"] = counts.get("requests", 0)
    report_path.write_text(json.dumps(clean(result)), encoding="utf-8")
    report_path.chmod(0o600)

def run_probe(apk):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return clean({"status": "requires_github_actions"})
    try:
        apk = Path(apk).resolve(strict=True)
        if not apk.is_file() or not 0 < apk.stat().st_size <= MAX_APK:
            return clean({"status": "invalid_apk"})
    except (OSError, ValueError):
        return clean({"status": "invalid_apk"})
    with tempfile.TemporaryDirectory(prefix="ipa-lab-anisette-") as directory:
        report = Path(directory) / "result.json"
        report.touch(mode=0o600)
        try:
            process = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), "--worker", str(apk), str(report)],
                cwd=directory, env={"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true", "LANG": "C.UTF-8"},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120,
            )
            if process.returncode != 0 or report.stat().st_size > 8192:
                return clean({"status": "worker_failed"})
            return clean(json.loads(report.read_text(encoding="utf-8")))
        except subprocess.TimeoutExpired:
            return clean({"status": "worker_timeout"})
        except Exception:
            return clean({"status": "worker_failed"})

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        result = clean({"status": "requires_github_actions"})
    elif len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]))
        return 0
    elif len(sys.argv) == 2:
        result = run_probe(sys.argv[1])
    else:
        result = clean({"status": "invalid_apk"})
    output = json.dumps(result, sort_keys=True)
    print(output)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("Account-free Anisette prerequisite experiment; not native login or FairPlay enrollment.\n\n")
            f.write(chr(96) * 3 + "json\n" + output + "\n" + chr(96) * 3 + "\n")
    return 0 if result["status"] == "complete" else 2

if __name__ == "__main__":
    raise SystemExit(main())
