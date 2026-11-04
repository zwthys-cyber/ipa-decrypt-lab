import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from private_export import ExportError, account_member, scrub_archive, validate_report

class PrivateExportTests(unittest.TestCase):
    def fixture(self, root):
        output = root/"out.ipa"
        output.write_bytes(b"synthetic-verified-output")
        before = {"binaries": [{"path": "Payload/Test.app/Test", "slices": [
            {"cpu_type": 1, "cpu_subtype": 2, "encryption": {"cryptid": 1, "offset": 4096, "size": 8192}}]}]}
        report = {"schema": "unfairplay-decryption-v2", "complete": True, "plaintext_verified": True,
            "encrypted_image_count": 1, "decrypted_page_count": 2,
            "account_data": {"stripped": True}, "output": {"sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
            "images": [{"member": "Payload/Test.app/Test", "slice_offset": 0, "cpu_type": 1, "cpu_subtype": 2,
                "pages": 2, "cryptoff": 4096, "cryptsize": 8192, "cryptid_before": 1, "cryptid_after": 0,
                "exact_mutation_scope": True, "plaintext_validation": "code-directory-pre-encryption-hashes",
                "pre_encryption_code_directories": [{"slot_count": 2, "matched_slots": 2}]}]}
        return output, before, report

    def test_complete_report_and_wrong_hash(self):
        with tempfile.TemporaryDirectory() as d:
            output, before, report = self.fixture(Path(d))
            self.assertEqual(validate_report(report, before, output), (1, 2))
            output.write_bytes(b"wrong bytes")
            with self.assertRaises(ExportError):
                validate_report(report, before, output)

    def test_reject_partial_or_flag_only_decryption(self):
        with tempfile.TemporaryDirectory() as d:
            output, before, base = self.fixture(Path(d))
            for field, value in (("complete", False), ("plaintext_verified", False),
                    ("encrypted_image_count", True), ("decrypted_page_count", 3), ("images", []),
                    ("account_data", {"stripped": False})):
                report = copy.deepcopy(base)
                report[field] = value
                with self.assertRaises(ExportError, msg=field):
                    validate_report(report, before, output)
            for field, value in (("pre_encryption_code_directories", []), ("member", "other"),
                    ("pages", 1), ("exact_mutation_scope", False),
                    ("pre_encryption_code_directories", [{"slot_count": 2, "matched_slots": 1}])):
                report = copy.deepcopy(base)
                report["images"][0][field] = value
                with self.assertRaises(ExportError, msg=field):
                    validate_report(report, before, output)

    def test_remove_all_store_metadata_and_licenses(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = Path(d)/"in.ipa", Path(d)/"clean.ipa"
            with zipfile.ZipFile(source, "w") as z:
                for name in ("iTunesMetadata.plist", "Payload/App.app/SC_Info/App.sinf",
                             "Payload/App.app/sc_info/", "loose.SUPF"):
                    z.writestr(name, "private-purchaser-data")
                z.writestr("Payload/App.app/App", b"unchanged-executable")
            scrub_archive(source, target)
            with zipfile.ZipFile(target) as z:
                self.assertEqual(z.namelist(), ["Payload/App.app/App"])
                self.assertEqual(z.read(z.namelist()[0]), b"unchanged-executable")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)

if __name__ == "__main__":
    unittest.main()
