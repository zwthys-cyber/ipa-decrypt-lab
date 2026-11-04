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
import anisette_probe as probe

class AnisetteProbeTests(unittest.TestCase):
    def headers(self):
        value = {key: base64.b64encode(b"synthetic-private-value").decode() for key in probe.REQUIRED}
        value["X-Apple-I-MD-RINFO"] = "1234"
        return value

    def successful(self):
        return {"status": "complete", **dict.fromkeys(probe.FLAGS, True), "apple_requests": 3}

    def test_transport_allows_only_apple_https_endpoints(self):
        for url in ("https://gsa.apple.com/grandslam/test", "https://apps.mzstatic.com/public.apk"):
            self.assertTrue(probe.allowed_url(url))
        for url in ("http://gsa.apple.com", "https://apple.com.evil.invalid", "https://evilapple.com",
                    "https://user:secret@gsa.apple.com", "https://gsa.apple.com:444",
                    "https://anisette.dl.mikealmel.ooo/libs", None):
            self.assertFalse(probe.allowed_url(url))

    def test_headers_are_validated_without_being_reported(self):
        value = self.headers()
        self.assertTrue(probe.headers_valid(value))
        for replacement in ("invalid base64!", "", True, "A" * 8193):
            with self.subTest(replacement_type=type(replacement).__name__):
                changed = dict(value, **{"X-Apple-I-MD": replacement})
                self.assertFalse(probe.headers_valid(changed))

    def test_claims_are_fail_closed_and_sensitive_fields_removed(self):
        raw = self.successful()
        raw.update(apple_login_attempted=True, native_state_imported=True, enrollment_created=True,
                   decryption_proven=True, headers=self.headers(), device="private", model="private")
        result = probe.clean(raw)
        self.assertEqual(result["status"], "complete")
        for key in ("apple_login_attempted", "native_state_imported", "enrollment_created", "decryption_proven"):
            self.assertIs(result[key], False)
        self.assertNotIn("private", json.dumps(result))
        raw["saved_state_reusable"] = 1
        self.assertEqual(probe.clean(raw)["status"], "worker_failed")

    def test_workspace_guard_precedes_filesystem_and_process_work(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(probe.subprocess, "run") as run:
            self.assertEqual(probe.run_probe("/missing")["status"], "requires_github_actions")
            run.assert_not_called()

    def test_worker_has_no_credentials_and_temporary_report_is_private_and_deleted(self):
        reports = []
        def child(command, **kwargs):
            self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
            self.assertNotIn("APPLE_ID", kwargs["env"])
            self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
            self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
            report = Path(command[-1])
            reports.append(report)
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            report.write_text(json.dumps(self.successful()))
            return SimpleNamespace(returncode=0)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "APPLE_ID": "private-account", "APPLE_PASSWORD": "private-password"
        }), patch.object(probe.subprocess, "run", side_effect=child):
            apk = Path(tmp) / "synthetic.apk"
            apk.write_bytes(b"synthetic")
            result = probe.run_probe(apk)
        self.assertEqual(result["status"], "complete")
        self.assertTrue(reports)
        self.assertTrue(all(not path.exists() for path in reports))

    def test_worker_timeout_and_malformed_output_fail_closed(self):
        for timeout in (False, True):
            def child(command, **kwargs):
                if timeout:
                    raise subprocess.TimeoutExpired(command, 120)
                Path(command[-1]).write_text("private-invalid-output")
                return SimpleNamespace(returncode=0)
            with self.subTest(timeout=timeout), tempfile.TemporaryDirectory() as tmp, patch.dict(
                os.environ, {"GITHUB_ACTIONS": "true"}
            ), patch.object(probe.subprocess, "run", side_effect=child):
                apk = Path(tmp) / "synthetic.apk"
                apk.write_bytes(b"synthetic")
                result = probe.run_probe(apk)
                self.assertEqual(result["status"], "worker_timeout" if timeout else "worker_failed")
                self.assertNotIn("private", json.dumps(result))

    def test_saved_state_reuse_is_required_before_success(self):
        class Provider:
            is_provisioned = True
            def provision(self): pass
            def get_data(inner): return self.headers()
            def save_all(self, state): state.write(b"private-synthetic-state")
        provider = Provider()
        for restored_ok in (False, True):
            restored = Provider()
            restored.is_provisioned = restored_ok
            module = SimpleNamespace(Anisette=SimpleNamespace(init=lambda path: provider, load=lambda state: restored))
            with self.subTest(restored_ok=restored_ok), tempfile.TemporaryDirectory() as tmp, patch.dict(
                sys.modules, {"anisette": module}
            ), patch.object(probe, "install_private_transport", return_value={"requests": 3}):
                report = Path(tmp) / "report.json"
                probe.worker(Path(tmp) / "unused.apk", report)
                result = json.loads(report.read_text())
                self.assertEqual(result["status"], "complete" if restored_ok else "session_restore_failed")
                self.assertNotIn("private", json.dumps(result))

if __name__ == "__main__":
    unittest.main()
