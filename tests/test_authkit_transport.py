import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import authkit_transport as transport

class TransportTests(unittest.TestCase):
    def test_reports_only_fixed_classifications_and_never_claims_authentication(self):
        result = transport.clean({"status": "transport_rejected", "error_domain": "NSCocoaErrorDomain",
            "error_code": 4099, "sdk_xpc_invalid_code": 4099, "service_missing": True,
            "raw_error": "private-account-and-path", "account_login_attempted": True,
            "enrollment_created": True, "decryption_proven": True})
        self.assertEqual(result["error_code"], 4099)
        self.assertTrue(result["service_missing"])
        self.assertNotIn("private", json.dumps(result))
        self.assertFalse(result["account_login_attempted"])
        self.assertFalse(result["enrollment_created"])
        self.assertFalse(result["decryption_proven"])
        result = transport.clean({"status": "private", "error_domain": "private", "error_code": True})
        self.assertNotIn("private", json.dumps(result))

    def test_connection_metadata_drops_unknown_services_and_raw_reasons(self):
        raw = {"status": "transport_rejected", "service_name": "com.apple.ak.auth.xpc",
               "raw_reason": "private-machine-and-account", "peer_pid": 1234,
               "invalidation_reason_present": True, "reason_peer_code_requirement": True}
        result = transport.clean(raw)
        self.assertEqual(result["service_name"], "com.apple.ak.auth.xpc")
        self.assertTrue(result["reason_peer_code_requirement"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("peer_pid", result)
        raw["service_name"] = "com.apple.ak.private-identifier"
        self.assertNotIn("service_name", transport.clean(raw))

    def test_reason_terms_and_signature_declarations_are_strict(self):
        raw = {"status": "transport_rejected", "invalidation_reason_terms": ["peer", "private-account", "peer", 1, {}],
               "declared_internal_authkit_entitlement": True, "signature_metadata_available": 1}
        result = transport.clean(raw)
        self.assertEqual(result["invalidation_reason_terms"], ["peer"])
        self.assertIs(result["declared_internal_authkit_entitlement"], True)
        self.assertNotIn("signature_metadata_available", result)
        self.assertNotIn("private", json.dumps(result))

    def test_native_launch_rejection_is_reported_without_native_text(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(
            transport.sys, "platform", "darwin"
        ), patch.object(transport.subprocess, "run", return_value=SimpleNamespace(
            returncode=-9, stdout="private-output", stderr="private-error"
        )):
            result = transport.probe("/synthetic", "named")
            self.assertEqual(result["status"], "native_process_failed")
            self.assertEqual(result["native_exit_code"], -9)
            self.assertTrue(result["native_process_signalled"])
            self.assertNotIn("private", json.dumps(result))

    def test_proxy_error_capture_is_bounded_sanitized_and_not_recursive(self):
        item = {"error_domain": "NSCocoaErrorDomain", "error_code": 4099, "raw_error": "private-secret",
                "service_name": "com.apple.ak.auth.xpc", "invalidation_reason_terms": ["connection", "private"],
                "observed_proxy_failures": [{"raw_error": "private-nested"}]}
        result = transport.clean({"observed_auth_proxy_requests": 2, "observed_proxy_failures": [item] * 8})
        self.assertEqual(result["observed_auth_proxy_requests"], 2)
        self.assertEqual(len(result["observed_proxy_failures"]), 4)
        self.assertNotIn("private", json.dumps(result))
        for row in result["observed_proxy_failures"]:
            self.assertNotIn("observed_proxy_failures", row)
            self.assertEqual(row["error_code"], 4099)

    def test_root_gui_control_preserves_target_session_and_clears_environment(self):
        def child(command, **kwargs):
            self.assertEqual(command[:4], ["/usr/bin/sudo", "-n", "/bin/launchctl", "asuser"])
            self.assertEqual(command[4], str(os.getuid()))
            self.assertEqual(command[5:9], ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin", "GITHUB_ACTIONS=true"])
            self.assertEqual(command[-1], "named")
            self.assertNotIn("APPLE_ID", kwargs["env"])
            self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
            return SimpleNamespace(returncode=0, stdout=json.dumps({
                "status": "transport_rejected", "effective_user_is_root": True}), stderr="")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "APPLE_ID": "private", "APPLE_PASSWORD": "private"}), patch.object(
            transport.sys, "platform", "darwin"
        ), patch.object(transport.subprocess, "run", side_effect=child):
            result = transport.probe("/synthetic", "named", scope="root_gui")
        self.assertIs(result["effective_user_is_root"], True)

    def test_bag_success_requires_completed_nonempty_error_free_response(self):
        value = {"status": "bag_fetch_succeeded", "callback_completed": True,
                 "bag_result_present": True, "error_present": False}
        self.assertEqual(transport.clean(value)["status"], "bag_fetch_succeeded")
        for key in ("callback_completed", "bag_result_present", "error_present"):
            broken = dict(value)
            broken.pop(key)
            self.assertEqual(transport.clean(broken)["status"], "probe_failed")

    def test_execution_guard_and_child_environment_exclude_credentials(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(transport.subprocess, "run") as run:
            self.assertEqual(transport.probe("/missing", "default")["status"], "requires_github_macos")
            run.assert_not_called()
        def child(*args, **kwargs):
            self.assertTrue(kwargs["capture_output"])
            self.assertNotIn("APPLE_ID", kwargs["env"])
            self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
            return SimpleNamespace(returncode=0, stdout=json.dumps({"status": "transport_rejected"}), stderr="")
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "APPLE_ID": "private",
                                     "APPLE_PASSWORD": "private"}), patch.object(
            transport.sys, "platform", "darwin"
        ), patch.object(transport.subprocess, "run", side_effect=child):
            self.assertEqual(transport.probe("/synthetic", "named")["status"], "transport_rejected")

    def test_connection_text_exposes_only_fixed_flags(self):
        result = transport.classify_connection_text(
            "Client org.ipa-lab.AuthKitTransport is missing entitlement com.apple.authkit.client.internal; private-identifier")
        self.assertTrue(result["entitlement_denial_phrase"])
        self.assertTrue(result["internal_authkit_entitlement_named"])
        self.assertTrue(result["own_client_named"])
        self.assertNotIn("private", json.dumps(result))
        result = transport.classify_connection_text("Entitlement com.apple.authkit.client.internal is present")
        self.assertFalse(result["entitlement_denial_phrase"])
        self.assertFalse(transport.classify_connection_text("x" * 1048577)["text_classification_available"])

    def test_daemon_log_counts_only_correlated_fixed_phrases(self):
        events = [
            {"processImagePath": "/system/akd", "eventMessage": "authkit-transport missing entitlement com.apple.authkit.client.internal private"},
            {"processImagePath": "/system/akd", "eventMessage": "another-client missing entitlement private"},
            {"processImagePath": "/system/another", "eventMessage": "AuthKitTransport missing entitlement private"},
        ]
        with patch.object(transport.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(events))):
            result = transport.daemon_diagnostic()
        self.assertEqual(result["status"], "queried")
        self.assertEqual(result["events"], 2)
        self.assertEqual(result["entitlement_denial_events"], 2)
        self.assertEqual(result["own_client_internal_entitlement_denial_events"], 1)
        self.assertNotIn("private", json.dumps(result))

    def test_timeout_and_invalid_native_output_are_not_reported(self):
        for output in ("private-invalid", "x" * 8193):
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(
                transport.sys, "platform", "darwin"
            ), patch.object(transport.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout=output)):
                result = transport.probe("/synthetic", "default")
                self.assertEqual(result["status"], "probe_failed")
                self.assertNotIn("private", json.dumps(result))
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(
            transport.sys, "platform", "darwin"
        ), patch.object(transport.subprocess, "run", side_effect=subprocess.TimeoutExpired("private", 20)):
            self.assertEqual(transport.probe("/synthetic", "default")["status"], "probe_failed")

if __name__ == "__main__":
    unittest.main()
