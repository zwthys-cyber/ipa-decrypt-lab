import contextlib
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import enrollment_environment as probe

class EnrollmentEnvironmentTests(unittest.TestCase):
    def result(self, status="native_login_unresolved"):
        return {"schema": "ipa-lab-enrollment-environment-v1", "status": "probe_complete",
                "authentication": {"status": status, "account_login_attempted": True,
                                   "password_submitted": True},
                "enrollment_created": False, "decryption_proven": False}

    def test_private_fields_and_error_text_are_never_published(self):
        raw = self.result("private-token-and-account")
        raw["account"] = "secret-account"
        raw["authentication"]["password"] = "secret-password"
        raw["ui_after"] = {"window_title": "secret-account",
                           "known_labels": ["sign_in", "secret-password", 99],
                           "word_flags": ["privacy", "secret-token"]}
        output = json.dumps(probe.clean(raw))
        for word in ("private-token", "secret-account", "secret-password", "secret-token"):
            self.assertNotIn(word, output)

    def test_ui_never_proves_enrollment_or_decryption(self):
        raw = self.result("native_ui_indicates_signed_in")
        raw.update(enrollment_created=True, decryption_proven=True)
        raw["authentication"].update(enrollment_created=True, decryption_proven=True)
        result = probe.clean(raw)
        for section in (result, result["authentication"]):
            self.assertIs(section["enrollment_created"], False)
            self.assertIs(section["decryption_proven"], False)

    def test_only_bounded_typed_ui_counts_are_accepted(self):
        raw = self.result()
        raw["ui_before"] = {"window_count": True, "text_fields": 513, "email_fields": 1,
                            "roles": {"AXTextField": 2, "private-role": 8}}
        result = probe.clean(raw)["ui_before"]
        self.assertNotIn("window_count", result)
        self.assertNotIn("text_fields", result)
        self.assertEqual(result["email_fields"], 1)
        self.assertEqual(result["roles"], {"AXTextField": 2})

    def test_incomplete_login_is_nonzero_even_when_probe_exits_zero(self):
        for status in ("native_login_form_unavailable", "native_login_rejected",
                       "native_verification_required", "native_login_unresolved"):
            with self.subTest(status=status), patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "LAB_NATIVE_UI_AUTH": "1"
            }, clear=True), patch("enrollment_environment.subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(self.result(status)), stderr="private native output"
            )) as run, contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(probe.main(), 2)
                self.assertIn("--authenticate", run.call_args.args[0])
                self.assertNotIn("private native output", output.getvalue())

    def test_account_free_probe_does_not_request_authentication(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True), patch(
            "enrollment_environment.subprocess.run", return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps(self.result()), stderr=""
            )
        ) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(probe.main(), 0)
            self.assertNotIn("--authenticate", run.call_args.args[0])

    def test_workspace_execution_is_rejected_before_launch(self):
        with patch.dict(os.environ, {}, clear=True), patch("enrollment_environment.subprocess.run") as run:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(), 2)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
