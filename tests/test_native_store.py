import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1]/"tools"))
from native_store import classify, download_diagnostics

class NativeStoreTests(unittest.TestCase):
    def test_generic_is_not_verification(self):
        r = SimpleNamespace(stdout="", stderr="apple_auth_ambiguous_bad_login", returncode=1)
        self.assertEqual(classify(r), "native_generic_bad_login")
    def test_success_requires_zero_exit(self):
        r = SimpleNamespace(stdout="login successful", stderr="error", returncode=1)
        self.assertNotEqual(classify(r), "authenticated")
    def test_signer_failure_separated(self):
        r = SimpleNamespace(stdout="", stderr="SAP certificate failure", returncode=1)
        self.assertEqual(classify(r), "native_signing_failed")

    def test_diagnostics_only_allow_fixed_markers(self):
        r = SimpleNamespace(stdout="email secret\\nIPA_LAB_STAGE:lookup_app\\nIPA_LAB_STAGE:secret\\n",
                            stderr="password secret", returncode=1)
        self.assertEqual(download_diagnostics(r), {"stage": "lookup_app", "exit_code": 1})
    def test_diagnostics_unknown_stage_is_not_exposed(self):
        r = SimpleNamespace(stdout="IPA_LAB_STAGE:account@example.com", stderr="", returncode=2)
        self.assertEqual(download_diagnostics(r), {"stage": "before_download", "exit_code": 2})
