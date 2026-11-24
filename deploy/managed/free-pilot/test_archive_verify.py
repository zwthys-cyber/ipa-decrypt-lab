"""Synthetic archives only. No external input or network."""
import hashlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import archive_verify as v


class ArchiveVerifyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "Synthetic.ipa"

    def tearDown(self):
        self.tmp.cleanup()

    def create(self, entries=None, method=zipfile.ZIP_STORED):
        if entries is None:
            entries = [("Payload/Synthetic.app/Info.plist", b"synthetic"),
                       ("Payload/Synthetic.app/content.bin", b"sample" * 2000),
                       ("Payload/Synthetic.app/empty.bin", b"")]
        with zipfile.ZipFile(self.path, "w", compression=method) as archive:
            for name, data in entries:
                archive.writestr(name, data)
        self.path.chmod(0o600)
        return self.path.read_bytes()

    def check(self, **kwargs):
        with self.path.open("rb") as stream:
            return v.verify(stream, **kwargs)

    def test_stored_and_deflated_preserved(self):
        for method in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raw = self.create(method=method)
            expected = hashlib.sha256(raw).hexdigest()
            result = self.check(ipa=True, expected=expected.upper())
            self.assertEqual(result["sha256"], expected)
            self.assertEqual(result["archive_bytes"], len(raw))
            self.assertEqual(result["entries"], 3)
            self.assertTrue(result["all_member_crc_verified"])
            self.assertTrue(result["expected_sha256_matched"])
            self.assertTrue(result["ipa_layout_present"])
            self.assertFalse(result["authenticity_verified"])
            self.assertFalse(result["installation_verified"])
            self.assertFalse(result["drm_status_verified"])
            self.assertEqual(self.path.read_bytes(), raw)

    def test_crc_failure(self):
        raw = bytearray(self.create())
        at = raw.index(b"sample" * 3)
        raw[at] ^= 1
        self.path.write_bytes(raw)
        with self.assertRaisesRegex(v.VerificationError, "member_integrity_failed"):
            self.check(ipa=True)

    def test_hash_mismatch(self):
        self.create()
        with self.assertRaisesRegex(v.VerificationError, "sha256_mismatch"):
            self.check(expected="0" * 64)

    def test_invalid_layout_and_unsafe_paths(self):
        self.create([("Plain.txt", b"content")])
        with self.assertRaisesRegex(v.VerificationError, "ipa_layout_invalid"):
            self.check(ipa=True)
        self.assertFalse(self.check()["ipa_layout_present"])
        self.create([("Payload/A.app/Info.plist", b"a"), ("Payload/B.app/Info.plist", b"b")])
        with self.assertRaisesRegex(v.VerificationError, "ipa_layout_invalid"):
            self.check(ipa=True)
        self.create([("../unsafe.txt", b"content")])
        with self.assertRaisesRegex(v.VerificationError, "archive_structure_invalid"):
            self.check()

    def test_private_file_and_cli_refusal(self):
        self.create()
        self.path.chmod(0o644)
        with self.assertRaisesRegex(v.VerificationError, "input_not_private"):
            self.check()
        self.path.chmod(0o600)
        with patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(v.main([str(self.path)]), 2)
            link = self.path.with_name("Link.ipa")
            link.symlink_to(self.path)
            self.assertEqual(v.main([str(link), "--confirm-authorized-file"]), 2)
            pipe = self.path.with_name("Pipe.zip")
            os.mkfifo(pipe, 0o600)
            self.assertEqual(v.main([str(pipe), "--confirm-authorized-file"]), 2)

    def test_size_policy_and_changed_input(self):
        self.create()
        with patch.object(v, "MAX_ARCHIVE", 10):
            with self.assertRaisesRegex(v.VerificationError, "archive_size_out_of_bounds"):
                self.check()
        original = v.snapshot
        with self.path.open("rb") as stream:
            before = original(stream)
            with patch.object(v, "snapshot", side_effect=[before, (*before[:-1], before[-1] + 1)]):
                with self.assertRaisesRegex(v.VerificationError, "input_changed"):
                    v.verify(stream)


if __name__ == "__main__":
    unittest.main()
