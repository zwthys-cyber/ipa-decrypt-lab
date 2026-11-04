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
    def setUp(self):
        state = patch("enrollment_environment.privileged_state", return_value={})
        state.start()
        self.addCleanup(state.stop)
        collector = patch("enrollment_environment.collect_auth_diagnostics", return_value={"capture_status": "ok"})
        self.collector = collector.start()
        self.addCleanup(collector.stop)

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
            self.collector.assert_not_called()

    def test_privileged_stat_distinguishes_denied_and_missing(self):
        for code, out, error, expected in [
            (0, "2048\n", "", "present_nonempty"), (0, "0\n", "", "present_empty"),
            (1, "", "stat: fixed path: No such file or directory", "not_found"),
            (1, "", "stat: fixed path: Operation not permitted", "inaccessible"),
            (1, "", "sudo: private detail", "stat_failed"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(probe.classify_stat(SimpleNamespace(returncode=code, stdout=out, stderr=error)), expected)

    def test_last_login_ui_contains_no_raw_dialog_or_values(self):
        raw = self.result()
        raw["authentication"]["last_ui"] = {
            "email_fields": 1, "secure_fields": 1, "sign_in_enabled": True,
            "email_value": "private-email", "password_value": "private-password",
            "error_kinds": ["cannot_connect", "private-dialog-text", {"secret": True}],
        }
        output = json.dumps(probe.clean(raw))
        self.assertIn("cannot_connect", output)
        self.assertNotIn("private", output)

    def test_ui_codes_are_strictly_bounded_integers(self):
        raw = self.result()
        raw["authentication"]["last_ui"] = {"error_codes": [-50, True, "private", 123456789, -50, 301]}
        self.assertEqual(probe.clean(raw)["authentication"]["last_ui"]["error_codes"], [-50, 301])

    def test_missing_or_timed_out_auth_window_never_queries_unrelated_logs(self):
        import subprocess
        for timeout in (False, True):
            with self.subTest(timeout=timeout), patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "LAB_NATIVE_UI_AUTH": "1", "LAB_NATIVE_AUTH_DIAGNOSTICS": "1"
            }, clear=True), patch("enrollment_environment.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=json.dumps(self.result("native_login_rejected")), stderr=""),
                side_effect=subprocess.TimeoutExpired("native", 220) if timeout else None
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                self.collector.reset_mock()
                self.assertEqual(probe.main(), 2)
                self.collector.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())["native_auth_diagnostics"],
                                 {"capture_status": "authentication_window_unavailable"})

    def test_auth_window_must_be_inside_child_and_excludes_non_auth_work(self):
        raw = self.result("native_login_rejected")
        for started, ended, expected in [
            (100, 110, (100, 110)), (90, 110, None), (100, 121, None),
            (100, 99, None), (True, 110, None), ("private", 110, None),
        ]:
            with self.subTest(started=started, ended=ended):
                raw["_authentication_window"] = {"started": started, "ended": ended}
                self.assertEqual(probe.authentication_window(raw, 95, 120), expected)
        raw["_authentication_window"] = {"started": 100, "ended": 300}
        self.assertIsNone(probe.authentication_window(raw, 90, 310))
        raw["_authentication_window"] = {"started": 100, "ended": 110}
        raw["authentication"]["account_login_attempted"] = False
        self.assertIsNone(probe.authentication_window(raw, 95, 120))

    def test_exact_auth_window_is_used_and_private_timestamps_are_not_reported(self):
        raw = self.result("native_login_rejected")
        raw["_authentication_window"] = {"started": 100, "ended": 110, "private": "secret"}
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "LAB_NATIVE_UI_AUTH": "1",
                                   "LAB_NATIVE_AUTH_DIAGNOSTICS": "1"}, clear=True), patch(
            "enrollment_environment.time.time", side_effect=[90, 120]
        ), patch("enrollment_environment.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout=json.dumps(raw), stderr="private native output"
        )), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(probe.main(), 2)
            self.collector.assert_called_once_with(100, ended=110)
        result = json.loads(output.getvalue())
        self.assertEqual(result["native_auth_diagnostics"]["window_seconds"], 10)
        self.assertEqual(result["native_auth_diagnostics"]["window_scope"], "credential_submission_to_terminal_ui")
        for key in ("_authentication_window", "started", "ended", "secret", "private native"):
            self.assertNotIn(key, output.getvalue())

    def test_workspace_execution_is_rejected_before_launch(self):
        with patch.dict(os.environ, {}, clear=True), patch("enrollment_environment.subprocess.run") as run:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(probe.main(), 2)
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
