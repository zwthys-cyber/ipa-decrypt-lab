import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_anisette_auth as auth

class NativeAnisetteAuthTests(unittest.TestCase):
    def success(self):
        return {
            "schema": "ipa-lab-native-anisette-auth-v1",
            "status": "native_authentication_succeeded",
            "account_login_attempted": True, "context_policy_verified": True,
            "provider_retained_by_context": True, "callback_completed": True,
            "idms_token_present": True, "account_identity_present": True,
            "provider_fetch_calls": 2, "errors": [],
        }

    def headers(self):
        encoded = base64.b64encode(b"synthetic-private-value").decode()
        return {"X-Apple-I-MD": encoded, "X-Apple-I-MD-M": encoded,
                "X-Apple-I-MD-LU": encoded, "X-Apple-I-MD-RINFO": "1234",
                "X-Mme-Device-Id": "synthetic-private-device"}

    def child(self, directory, body):
        script = Path(directory) / "synthetic-child"
        script.write_text("#!" + sys.executable + "\nimport json, sys, time\n" + body)
        script.chmod(0o700)
        return script

    def test_success_requires_callback_policy_token_identity_and_provider(self):
        self.assertEqual(auth.clean(self.success())["status"], "native_authentication_succeeded")
        for key, value in (("account_login_attempted", False), ("context_policy_verified", 1),
                           ("provider_retained_by_context", False), ("callback_completed", False),
                           ("idms_token_present", False), ("account_identity_present", False),
                           ("provider_fetch_calls", 0), ("provider_fetch_calls", 5),
                           ("errors", [{"domain": "AKAnisetteError", "code": -8008}])):
            raw = dict(self.success(), **{key: value})
            self.assertEqual(auth.clean(raw)["status"], "native_auth_result_unverified")

    def test_reports_drop_sensitive_values_and_cannot_claim_enrollment(self):
        raw = dict(self.success(), headers=self.headers(), token="private-token",
                   native_account_created=True, store_session_created=True,
                   enrollment_created=True, decryption_proven=True)
        result = auth.clean(raw)
        self.assertNotIn("private", json.dumps(result))
        for key in ("native_account_created", "store_session_created", "enrollment_created", "decryption_proven"):
            self.assertIs(result[key], False)
        result = auth.clean({"status": "native_auth_rejected", "errors": [
            {"domain": "private-domain", "code": 1},
            {"domain": "AKAnisetteError", "code": -8008, "description": "private-secret"},
            {"domain": "AKAnisetteError", "code": True}]})
        self.assertEqual(result["errors"], [{"domain": "AKAnisetteError", "code": -8008}])
        self.assertNotIn("private", json.dumps(result))

    def test_child_environment_has_only_explicitly_needed_credentials(self):
        with patch.dict(os.environ, {"APPLE_ID": "private-account", "APPLE_PASSWORD": "private-password",
                                     "GITHUB_TOKEN": "private-repository-token", "UNRELATED": "private"}, clear=True):
            self.assertNotIn("APPLE_ID", auth.native_environment())
            self.assertNotIn("APPLE_PASSWORD", auth.native_environment())
            env = auth.native_environment(credentials=True)
            self.assertEqual(env["APPLE_PASSWORD"], "private-password")
            self.assertNotIn("GITHUB_TOKEN", env)
            self.assertNotIn("UNRELATED", env)

    def test_workspace_and_missing_credentials_guards_precede_process_work(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(auth.subprocess, "Popen") as popen:
            self.assertEqual(auth.run_worker("/missing", "/missing")["status"], "requires_github_macos")
            popen.assert_not_called()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True), patch.object(
            auth.sys, "platform", "darwin"
        ), patch.object(auth.subprocess, "Popen") as popen:
            self.assertEqual(auth.run_worker("/missing", "/missing")["status"], "missing_credentials")
            popen.assert_not_called()

    def test_device_context_is_private_bounded_and_strict(self):
        device = {"uniqueDeviceIdentifier": "private-device", "localUserUUID": "private-user",
                  "serverFriendlyDescription": "private-description"}
        def child(command, **kwargs):
            self.assertTrue(kwargs["capture_output"])
            self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
            return SimpleNamespace(returncode=0, stdout=json.dumps(device))
        with patch.object(auth.subprocess, "run", side_effect=child):
            self.assertEqual(auth.private_device_context("/synthetic"), device)
        for output in ("private-invalid-json", json.dumps(dict(device, token="private")), "x" * 8193):
            with patch.object(auth.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)):
                with self.assertRaises(ValueError):
                    auth.private_device_context("/synthetic")

    def test_real_private_pipe_generates_fresh_data_on_each_callback(self):
        count = []
        def get_data():
            count.append(1)
            return self.headers()
        body = """for _ in range(2):
    print(json.dumps({"request": "anisette"}), flush=True)
    value = json.loads(sys.stdin.readline())
    assert value["device"] == {"synthetic": "private-device"}
    assert "X-Apple-I-MD" in value["headers"]
print(json.dumps(""" + repr(self.success()) + """), flush=True)
"""
        with tempfile.TemporaryDirectory() as directory:
            result = auth.exchange(self.child(directory, body), SimpleNamespace(get_data=get_data),
                                   {"synthetic": "private-device"}, timeout=5)
        self.assertEqual(len(count), 2)
        self.assertEqual(result["fresh_data_requests"], 2)
        self.assertEqual(result["status"], "native_authentication_succeeded")
        self.assertNotIn("private", json.dumps(result))

    def test_unexpected_output_and_invalid_headers_abort_without_forwarding_values(self):
        cases = [('print(json.dumps({"token": "private-secret"}), flush=True)\n', self.headers()),
                 ('print(json.dumps({"request": "anisette"}), flush=True)\nsys.stdin.readline()\n', {})]
        for body, headers in cases:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError) as raised:
                    auth.exchange(self.child(directory, body), SimpleNamespace(get_data=lambda: headers), {}, timeout=2)
                self.assertEqual(str(raised.exception), "bridge_protocol_failed")

    def test_callback_budget_timeout_and_failed_exit_are_fail_closed(self):
        body = """for _ in range(5):
    print(json.dumps({"request": "anisette"}), flush=True)
    sys.stdin.readline()
"""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                auth.exchange(self.child(directory, body), SimpleNamespace(get_data=self.headers), {}, timeout=3)
            result = auth.exchange(self.child(directory, "time.sleep(5)\n"),
                                   SimpleNamespace(get_data=self.headers), {}, timeout=0.1)
            self.assertEqual(result["status"], "native_auth_timeout")
            result = auth.exchange(self.child(directory, "print(json.dumps(" + repr(self.success()) +
                "), flush=True)\nsys.exit(2)\n"), SimpleNamespace(get_data=self.headers), {}, timeout=3)
            self.assertEqual(result["status"], "native_auth_result_unverified")

    def test_worker_reports_stage_after_successful_provisioning_without_exception_text(self):
        device = {"uniqueDeviceIdentifier": "private-device", "localUserUUID": "private-user",
                  "serverFriendlyDescription": "private-description"}
        provider = SimpleNamespace(provision=lambda: None, is_provisioned=True)
        modules = {"anisette": SimpleNamespace(Anisette=SimpleNamespace(init=lambda *a, **k: provider)),
                   "anisette._device": SimpleNamespace(AnisetteDeviceConfig=lambda **k: k)}
        with tempfile.TemporaryDirectory() as directory, patch.dict(sys.modules, modules), patch.object(
            auth, "private_device_context", return_value=device
        ), patch.object(auth, "install_private_transport", return_value={"requests": 3}), patch.object(
            auth, "exchange", side_effect=ValueError("private-secret")
        ):
            report = Path(directory) / "result.json"
            auth.worker(Path(directory) / "unused.apk", Path("/unused"), report)
            result = json.loads(report.read_text())
            self.assertEqual(result["status"], "bridge_protocol_failed")
            self.assertTrue(result["provider_initialization_succeeded"])
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("private", json.dumps(result))

if __name__ == "__main__":
    unittest.main()
