"""Synthetic-only contract tests. Run by GitHub Actions, never on the server."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ENGINE = str(Path(sys.argv.pop(1)).resolve())

def image(cryptid=1, cryptoff=4096, cryptsize=4096, commands=None):
    command = struct.pack("<6I", 0x2C, 24, cryptoff, cryptsize, cryptid, 0)
    if commands is None:
        commands = command
    header = struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 2, 1, len(commands), 0, 0)
    return (header + commands).ljust(8192, b"\x00")

class Contracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
    def run_image(self, data):
        p = self.root / "sample"
        p.write_bytes(data)
        return subprocess.run([ENGINE, "inspect", str(p)], capture_output=True, text=True, timeout=5)
    def test_probe_does_not_claim_decryption(self):
        r = subprocess.run([ENGINE, "probe"], check=True, capture_output=True, text=True, timeout=5)
        report = json.loads(r.stdout)
        self.assertIs(report["decryption_proven"], False)
        self.assertIs(report["account_authorization_verified"], False)
    def test_encrypted_flag_is_reported(self):
        r = self.run_image(image())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["cryptid"], 1)
    def test_clear_flag_is_not_runtime_verification(self):
        r = self.run_image(image(cryptid=0))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIs(json.loads(r.stdout)["runtime_verified"], False)
    def test_out_of_bounds_rejected(self):
        self.assertNotEqual(self.run_image(image(cryptoff=8190, cryptsize=100)).returncode, 0)
    def test_encryption_over_header_rejected(self):
        self.assertNotEqual(self.run_image(image(cryptoff=32)).returncode, 0)
    def test_truncated_input_rejected(self):
        self.assertNotEqual(self.run_image(b"\xcf\xfa\xed\xfe").returncode, 0)
    def test_overflow_load_command_rejected(self):
        data = bytearray(image())
        struct.pack_into("<I", data, 36, 0xFFFFFFF8)
        self.assertNotEqual(self.run_image(data).returncode, 0)
    def test_zero_size_load_command_rejected(self):
        data = bytearray(image())
        struct.pack_into("<I", data, 36, 0)
        self.assertNotEqual(self.run_image(data).returncode, 0)
    def test_duplicate_encryption_rejected(self):
        data = bytearray(image())
        command = data[32:56]
        struct.pack_into("<II", data, 16, 2, 48)
        data[56:80] = command
        self.assertNotEqual(self.run_image(data).returncode, 0)
    def test_zip_is_not_a_macho(self):
        self.assertNotEqual(self.run_image(b"PK\x03\x04" + bytes(100)).returncode, 0)
    def test_existing_output_is_preserved(self):
        source = self.root / "input"
        source.write_bytes(image(cryptid=0))
        output = self.root / "candidate"
        output.write_bytes(b"keep")
        r = subprocess.run([ENGINE, "attempt", str(source), str(output)], capture_output=True, timeout=35)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(output.read_bytes(), b"keep")
    def test_unencrypted_attempt_creates_no_output(self):
        source = self.root / "input"
        source.write_bytes(image(cryptid=0))
        output = self.root / "candidate"
        r = subprocess.run([ENGINE, "attempt", str(source), str(output)], capture_output=True, timeout=35)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse(output.exists())

if __name__ == "__main__":
    unittest.main()
