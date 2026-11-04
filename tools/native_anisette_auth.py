"""One private native AuthKit attempt using freshly generated independent Anisette data."""
import json
import logging
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from anisette_probe import MAX_APK, headers_valid, install_private_transport

NATIVE_STATUSES = {
    "interface_unavailable", "authentication_not_enabled", "contract_failed", "device_context_unavailable",
    "missing_credentials", "context_policy_unavailable", "native_auth_timeout", "native_auth_rejected",
    "native_authentication_succeeded", "native_auth_result_unverified", "native_exception",
    "private_device_context_failed", "provider_provisioning_failed", "bridge_protocol_failed",
    "worker_failed", "worker_timeout", "requires_github_macos", "invalid_input",
}
BOOLS = {"account_login_attempted", "context_policy_verified", "provider_retained_by_context",
         "callback_completed", "result_dictionary_present", "idms_token_present", "account_identity_present",
         "provider_initialization_succeeded", "native_device_context_used"}
COUNTS = {"provider_fetch_calls": 4, "provider_other_calls": 32, "default_service_type": 64,
          "fresh_data_requests": 4, "apple_provisioning_requests": 8}
DOMAINS = {"AKAuthenticationError", "AKAuthenticationServerError", "AKAnisetteError",
           "AKUnderlyingADIErrors", "AKAttestationErrorDomain", "com.apple.AppleIDAuthSupport",
           "com.apple.devicecheck.error.baa", "NSCocoaErrorDomain", "NSPOSIXErrorDomain",
           "NSURLErrorDomain", "IPALab.Anisette"}

def clean(value):
    result = {"schema": "ipa-lab-native-anisette-auth-v1", "status": "worker_failed",
              "native_account_created": False, "store_session_created": False,
              "enrollment_created": False, "decryption_proven": False}
    if not isinstance(value, dict):
        return result
    status = value.get("status")
    if type(status) is str and status in NATIVE_STATUSES:
        result["status"] = status
    for key in BOOLS:
        if type(value.get(key)) is bool:
            result[key] = value[key]
    for key, maximum in COUNTS.items():
        if type(value.get(key)) is int and 0 <= value[key] <= maximum:
            result[key] = value[key]
    errors = value.get("errors", [])
    if isinstance(errors, list):
        result["errors"] = [{"domain": e["domain"], "code": e["code"]} for e in errors[:8]
            if isinstance(e, dict) and type(e.get("domain")) is str and e["domain"] in DOMAINS
            and type(e.get("code")) is int and -999999 <= e["code"] <= 999999]
    if result["status"] == "native_authentication_succeeded":
        required = ("account_login_attempted", "context_policy_verified", "provider_retained_by_context",
                    "callback_completed", "idms_token_present", "account_identity_present")
        if (not all(result.get(key) is True for key in required)
                or not 1 <= result.get("provider_fetch_calls", 0) <= 4
                or result.get("errors") != []):
            result["status"] = "native_auth_result_unverified"
    return result

def native_environment(credentials=False):
    env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true", "LAB_NATIVE_BRIDGE_PRIVATE_IPC": "1"}
    if credentials:
        env.update(LAB_NATIVE_BRIDGE_AUTH="1",
                   APPLE_ID=os.environ.get("APPLE_ID", ""), APPLE_PASSWORD=os.environ.get("APPLE_PASSWORD", ""))
    return env

def private_device_context(bridge):
    run = subprocess.run([str(bridge), "--device-context"], capture_output=True, text=True,
                         stdin=subprocess.DEVNULL, env=native_environment(), timeout=15)
    if run.returncode != 0 or len(run.stdout) > 8192:
        raise ValueError("private_device_context_failed")
    value = json.loads(run.stdout)
    keys = {"uniqueDeviceIdentifier", "localUserUUID", "serverFriendlyDescription"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("private_device_context_failed")
    if any(type(v) is not str or not 0 < len(v) <= 2048 for v in value.values()):
        raise ValueError("private_device_context_failed")
    return value

def exchange(bridge, provider, device, timeout=60):
    """Private request/response pipe; fresh OTP data is generated for each callback."""
    child = subprocess.Popen([str(bridge), "--authenticate"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=native_environment(credentials=True))
    selector = selectors.DefaultSelector()
    selector.register(child.stdout, selectors.EVENT_READ)
    buffer = bytearray()
    requested = 0
    result = None
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and result is None:
            if not selector.select(min(0.2, max(0, deadline - time.monotonic()))):
                continue
            block = os.read(child.stdout.fileno(), 8192)
            if not block:
                break
            buffer.extend(block)
            if len(buffer) > 32768:
                raise ValueError("bridge_protocol_failed")
            while b"\n" in buffer:
                line, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)
                item = json.loads(line)
                if item == {"request": "anisette"}:
                    requested += 1
                    if requested > 4:
                        raise ValueError("bridge_protocol_failed")
                    headers = provider.get_data()
                    if not headers_valid(headers):
                        raise ValueError("bridge_protocol_failed")
                    payload = json.dumps({"headers": headers, "device": device}).encode() + b"\n"
                    if len(payload) > 32768:
                        raise ValueError("bridge_protocol_failed")
                    child.stdin.write(payload)
                    child.stdin.flush()
                elif isinstance(item, dict) and item.get("schema") == "ipa-lab-native-anisette-auth-v1":
                    result = clean(item)
                    break
                else:
                    raise ValueError("bridge_protocol_failed")
        if result is None:
            return clean({"status": "native_auth_timeout" if time.monotonic() >= deadline else "bridge_protocol_failed",
                          "fresh_data_requests": min(requested, 4)})
        child.wait(timeout=5)
        if child.returncode != 0 and result["status"] == "native_authentication_succeeded":
            result["status"] = "native_auth_result_unverified"
        result["fresh_data_requests"] = requested
        return clean(result)
    finally:
        selector.close()
        if child.poll() is None:
            child.kill()
        child.wait()
        child.stdin.close()
        child.stdout.close()
        buffer.clear()

def worker(apk, bridge, report):
    logging.disable(logging.CRITICAL)
    result = {"status": "private_device_context_failed"}
    counts = {}
    try:
        device = private_device_context(bridge)
        result["native_device_context_used"] = True
        result["status"] = "provider_provisioning_failed"
        from anisette import Anisette
        from anisette._device import AnisetteDeviceConfig
        import secrets
        config = AnisetteDeviceConfig(
            server_friendly_description=device["serverFriendlyDescription"],
            unique_device_id=device["uniqueDeviceIdentifier"],
            local_user_uuid=device["localUserUUID"], adi_id=secrets.token_hex(8))
        counts = install_private_transport()
        provider = Anisette.init(str(apk), default_device_config=config)
        provider.provision()
        if provider.is_provisioned is not True:
            raise ValueError("provider_provisioning_failed")
        result["provider_initialization_succeeded"] = True
        result["status"] = "bridge_protocol_failed"
        native = exchange(bridge, provider, device)
        result.update(native)
    except Exception:
        # Keep only the stage, never a private exception or subprocess output.
        pass
    result["apple_provisioning_requests"] = counts.get("requests", 0)
    report.write_text(json.dumps(clean(result)), encoding="utf-8")
    report.chmod(0o600)

def run_worker(apk, bridge, timeout=180):
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        return clean({"status": "requires_github_macos"})
    if not os.environ.get("APPLE_ID") or not os.environ.get("APPLE_PASSWORD"):
        return clean({"status": "missing_credentials"})
    try:
        apk, bridge = Path(apk).resolve(strict=True), Path(bridge).resolve(strict=True)
        if not 0 < apk.stat().st_size <= MAX_APK or not bridge.is_file():
            return clean({"status": "invalid_input"})
    except (OSError, ValueError):
        return clean({"status": "invalid_input"})
    with tempfile.TemporaryDirectory(prefix="ipa-lab-native-auth-") as directory:
        report = Path(directory) / "result.json"
        report.touch(mode=0o600)
        child = None
        try:
            child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker",
                str(apk), str(bridge), str(report)], cwd=directory,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=native_environment(credentials=True), start_new_session=True)
            child.wait(timeout=timeout)
            if child.returncode != 0 or report.stat().st_size > 8192:
                return clean({"status": "worker_failed"})
            return clean(json.loads(report.read_text(encoding="utf-8")))
        except subprocess.TimeoutExpired:
            return clean({"status": "worker_timeout"})
        except Exception:
            return clean({"status": "worker_failed"})
        finally:
            if child is not None:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()

def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin":
        result = clean({"status": "requires_github_macos"})
    elif len(sys.argv) == 5 and sys.argv[1] == "--worker":
        worker(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
        return 0
    elif len(sys.argv) == 3:
        result = run_worker(sys.argv[1], sys.argv[2])
    else:
        result = clean({"status": "invalid_input"})
    output = json.dumps(result, sort_keys=True)
    print(output)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("Single ephemeral AuthKit research attempt. No Store enrollment/model is established.\n\n"
                    + chr(96) * 3 + "json\n" + output + "\n" + chr(96) * 3 + "\n")
    return 0 if result["status"] == "native_authentication_succeeded" else 2

if __name__ == "__main__":
    raise SystemExit(main())
