import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1]/"tools"))
from store_download import app_id, login

def response(code=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)

class StoreDownloadTests(unittest.TestCase):
    def test_id_and_link(self):
        self.assertEqual(app_id("6599842047"), "6599842047")
        self.assertEqual(app_id("https://apps.apple.com/us/app/a/id6599842047?l=zh"), "6599842047")
    def test_untrusted_link_rejected(self):
        for value in ["https://example.com/id6599842047", "6599842047; echo leak", "-1"]:
            with self.assertRaises(ValueError):
                app_id(value)
    def test_zero_exit_two_factor_is_not_success(self):
        def run(*args):
            return response(stdout="2FA code is required; --auth-code")
        self.assertEqual(login("tool", "private", "private", "", "private", run), "requires_2fa")
    def test_auth_failure_not_downloaded(self):
        self.assertEqual(login("tool","e","p","","k",lambda *a: response(1)), "authentication_failed")
    def test_session_is_independently_checked(self):
        results = iter([response(), response(1)])
        self.assertEqual(login("tool","e","p","","k",lambda *a: next(results)), "session_unverified")
    def test_success_requires_session(self):
        results = iter([response(), response()])
        self.assertEqual(login("tool","e","p","123456","k",lambda *a: next(results)), "authenticated")
