import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1]/"tools"))
from native_store import classify

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
