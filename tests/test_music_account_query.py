import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import music_account_query as q

def base(status):
    return dict(status=status, **{k: False for k in q.FORBIDDEN})

class MusicQueryPrivacyTests(unittest.TestCase):
    def test_strip_account_material_and_unknown_ui_text(self):
        raw = base("signin_unconfirmed")
        raw.update(password="DO-NOT-EXPORT", email="private@example.invalid",
                   screens={"after_password": {"labels": {"password": 1, "DO-NOT-EXPORT": 1},
                                                "roles": {"AXTextField": 1},
                                                "raw_text": "DO-NOT-EXPORT"}})
        encoded = json.dumps(q.clean(raw))
        self.assertNotIn("DO-NOT-EXPORT", encoded)
        self.assertNotIn("private@example.invalid", encoded)
        self.assertEqual(q.clean(raw)["screens"]["after_password"]["labels"], {"password": 1})

    def test_count_requires_all_evidence(self):
        raw = base("count_retrieved")
        raw.update({k: True for k in q.COUNT_EVIDENCE})
        raw["authorized_computer_count"] = 5
        self.assertEqual(q.clean(raw)["authorized_computer_count"], 5)
        for key in q.COUNT_EVIDENCE:
            with self.subTest(key=key):
                bad = dict(raw, **{key: False})
                self.assertEqual(q.clean(bad)["status"], "invalid_report")
                self.assertNotIn("authorized_computer_count", q.clean(bad))

    def test_associated_devices_bool_and_string_are_not_computer_counts(self):
        raw = base("count_retrieved")
        raw.update({k: True for k in q.COUNT_EVIDENCE})
        for value in (True, "5", 10, -1, 5.0, None):
            with self.subTest(value=value):
                self.assertEqual(q.clean(dict(raw, authorized_computer_count=value))["status"], "invalid_report")

    def test_unexpected_mutation_invalidates_result(self):
        for key in q.FORBIDDEN:
            raw = base("count_retrieved")
            raw.update({k: True for k in q.COUNT_EVIDENCE})
            raw.update(authorized_computer_count=5, **{key: True})
            self.assertEqual(q.clean(raw)["status"], "unexpected_account_mutation")
            self.assertNotIn("authorized_computer_count", q.clean(raw))

    def test_preflight_cannot_submit_credentials(self):
        raw = base("preflight_ready")
        raw.update(email_form_ready=True, synthetic_email_fill_ready=True, synthetic_email_cleared=True,
                   credentials_used=False, email_submit_attempted=False, password_submit_attempted=False)
        self.assertEqual(q.clean(raw)["status"], "preflight_ready")
        self.assertEqual(q.clean(dict(raw, email_submit_attempted=True))["status"], "invalid_report")

    def test_credentials_only_in_private_stdin(self):
        process = Mock()
        process.returncode = 0
        process.communicate.return_value = (json.dumps(base("signin_unconfirmed")).encode(), None)
        with patch.dict(os.environ, {"APPLE_ID": "private@example.invalid", "APPLE_PASSWORD": "PRIVATE-PASSWORD"}):
            with patch.object(q.subprocess, "Popen", return_value=process) as popen:
                q.run("/safe/binary")
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/safe/binary"])
        self.assertNotIn("APPLE_ID", kwargs["env"])
        self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        payload = json.loads(process.communicate.call_args.args[0])
        self.assertEqual(payload["password"], "PRIVATE-PASSWORD")

    def test_preflight_uses_no_secret_stdin(self):
        process = Mock()
        process.returncode = 1
        process.communicate.return_value = (b"PRIVATE-PASSWORD", None)
        with patch.object(q.subprocess, "Popen", return_value=process):
            result = q.run("/safe/binary", preflight=True)
        self.assertIsNone(process.communicate.call_args.args[0])
        self.assertNotIn("PRIVATE-PASSWORD", json.dumps(result))

    def test_timeout_kills_process_group(self):
        process = Mock(pid=1234)
        process.communicate.side_effect = [subprocess.TimeoutExpired("private", 125), (b"PRIVATE-PASSWORD", None)]
        with patch.object(q.subprocess, "Popen", return_value=process), patch.object(q.os, "killpg") as kill:
            result = q.run("/safe/binary", preflight=True)
        kill.assert_called_once_with(1234, q.signal.SIGKILL)
        self.assertEqual(result["status"], "native_timeout")

if __name__ == "__main__":
    unittest.main()
