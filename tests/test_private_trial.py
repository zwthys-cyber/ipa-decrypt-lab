from pathlib import Path
import sys, tempfile, unittest, zipfile
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import private_trial

class TrialTests(unittest.TestCase):
    def test_store_page_is_not_download(self):
        with self.assertRaises(ValueError):
            private_trial.check_url("https://apps.apple.com/us/app/id6599842047")
    def test_plain_http_rejected(self):
        with self.assertRaises(ValueError):
            private_trial.check_url("http://example.com/sample.ipa")
    def test_embedded_credentials_rejected(self):
        with self.assertRaises(ValueError):
            private_trial.check_url("https://user:password@example.com/a.ipa")
    def test_signed_https_allowed(self):
        private_trial.check_url("https://example.com/a.ipa?signature=synthetic")
    def test_extractor_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d)/"bad.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("../escape", b"synthetic")
            with self.assertRaises(ValueError):
                private_trial.extract_checked(archive, Path(d)/"out")
            self.assertFalse((Path(d)/"escape").exists())
    def test_license_path_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            archive = Path(d)/"sample.zip"
            name = "Payload/Synthetic.app/SC_Info/Synthetic.sinf"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr(name, b"synthetic-not-a-license")
            private_trial.extract_checked(archive, Path(d)/"out")
            self.assertEqual((Path(d)/"out"/name).read_bytes(), b"synthetic-not-a-license")
