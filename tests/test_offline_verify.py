import base64
import json
import os
from pathlib import Path
import stat
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1]/"tools"))
import offline_verify

class OfflineVerifierTests(unittest.TestCase):
    def report(self, **changes):
        value = dict(schema="unfairplay-model-verification-v2", success=True,
                     plaintext_retained=False, plaintext_verified=True,
                     encrypted_images=2, decrypted_pages=10,
                     logical_key_sha256_by_sinf={"private-path": "private-hash"})
        value.update(changes)
        return value
    def test_missing_model_never_launches_backend(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with patch("offline_verify.subprocess.run") as run:
                result = offline_verify.verify("unused", "unused")
                self.assertEqual(result["status"], "missing_enrollment_model")
                run.assert_not_called()
    def test_zero_exit_unverified_plaintext_is_not_success(self):
        result = offline_verify.sanitized_report(self.report(plaintext_verified=False), 2)
        self.assertEqual(result["status"], "offline_plaintext_unverified")
        self.assertFalse(result["decryption_proven"])
    def test_full_coverage_required(self):
        result = offline_verify.sanitized_report(self.report(encrypted_images=1), 2)
        self.assertEqual(result["status"], "offline_invalid_report")
    def test_flags_must_be_booleans(self):
        for changes in ({"success": 1}, {"plaintext_verified": "true"}, {"encrypted_images": True}):
            self.assertEqual(offline_verify.sanitized_report(self.report(**changes), 2)["status"],
                             "offline_invalid_report")
    def test_report_redacts_private_fields_and_never_claims_runtime(self):
        result = offline_verify.sanitized_report(self.report(), 2)
        self.assertTrue(result["plaintext_verified"])
        self.assertNotIn("private", json.dumps(result))
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["plaintext_retained"])
    def test_malformed_model_stops_before_execution(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "FAIRPLAY_MODEL_B64": "not base64"}, clear=True):
            self.assertEqual(offline_verify.verify("unused", "unused")["status"], "invalid_enrollment_model_encoding")
    def test_model_permissions_environment_redaction_and_cleanup(self):
        model_paths = []
        with patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "FAIRPLAY_MODEL_B64": base64.b64encode(b"synthetic-model").decode(),
            "APPLE_ID": "secret-user", "APPLE_PASSWORD": "secret-password",
        }, clear=True), patch("offline_verify.audit", return_value={"encrypted_slice_count": 2}):
            def runner(command, **kwargs):
                model = Path(command[command.index("--model")+1])
                model_paths.append(model)
                self.assertEqual(stat.S_IMODE(model.stat().st_mode), 0o600)
                self.assertEqual(model.read_bytes(), b"synthetic-model")
                self.assertNotIn("APPLE_ID", kwargs["env"])
                self.assertNotIn("APPLE_PASSWORD", kwargs["env"])
                self.assertNotIn("FAIRPLAY_MODEL_B64", kwargs["env"])
                return SimpleNamespace(returncode=1, stdout="secret", stderr="private error")
            result = offline_verify.verify("unused", "unused", runner)
        self.assertEqual(result["status"], "offline_verification_rejected")
        self.assertFalse(model_paths[0].exists())
        self.assertNotIn("private error", json.dumps(result))

    def test_native_pipeline_stops_before_metadata_or_login(self):
        import native_store
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}, clear=True):
            with patch("native_store.metadata") as metadata, patch("native_store.run") as run:
                result = native_store.trial("unused", "unused", "6599842047", offline_binary="unused")
                self.assertEqual(result["status"], "missing_enrollment_model")
                metadata.assert_not_called()
                run.assert_not_called()
