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
            return SimpleNamespace(returncode=0, stdout=json.dumps({"status": "transport_rejected"}))
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "APPLE_ID": "private",
                                     "APPLE_PASSWORD": "private"}), patch.object(
            transport.sys, "platform", "darwin"
        ), patch.object(transport.subprocess, "run", side_effect=child):
            self.assertEqual(transport.probe("/synthetic", "named")["status"], "transport_rejected")

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
