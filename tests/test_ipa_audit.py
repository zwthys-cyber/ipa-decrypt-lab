import importlib.util
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("ipa_audit", Path(__file__).parents[1] / "tools" / "ipa_audit.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def image(cryptid=1):
    h = struct.pack("<8I", 0xFEEDFACF, 0x0100000C, 0, 2, 1, 24, 0, 0)
    c = struct.pack("<6I", 0x2C, 24, 4096, 4096, cryptid, 0)
    return (h + c).ljust(8192, b"\0")

def fat():
    first, second = image(0), bytearray(image(1))
    struct.pack_into("<I", second, 8, 2)
    h = struct.pack(">II", 0xCAFEBABE, 2)
    h += struct.pack(">5I", 0x0100000C, 0, 4096, len(first), 12)
    h += struct.pack(">5I", 0x0100000C, 2, 12288, len(second), 12)
    return h.ljust(4096, b"\0") + first + second

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.ipa"
    def make(self, binary=None, extras=()):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("Payload/Demo.app/Info.plist", plistlib.dumps({
                "CFBundleIdentifier": "example.synthetic", "CFBundleExecutable": "Demo",
                "CFBundleShortVersionString": "0.0.1"}))
            if binary is not None:
                z.writestr("Payload/Demo.app/Demo", binary)
            for name, data in extras:
                z.writestr(name, data)
    def test_main_widget_framework_are_all_audited(self):
        self.make(image(0), [
            ("Payload/Demo.app/PlugIns/Widget.appex/Widget", image(1)),
            ("Payload/Demo.app/Frameworks/Demo.framework/Demo", image(1))])
        result = audit.audit(self.path)
        self.assertEqual(result["binary_count"], 3)
        self.assertEqual(result["encrypted_slice_count"], 2)
        self.assertFalse(result["plaintext_verified"])
    def test_clear_flags_never_claim_plaintext(self):
        self.make(image(0))
        result = audit.audit(self.path)
        self.assertEqual(result["status"], "no_encrypted_flags_found")
        self.assertFalse(result["runtime_verified"])
    def test_missing_main_rejected(self):
        self.make()
        with self.assertRaises(audit.AuditError):
            audit.audit(self.path)
    def test_path_traversal_rejected(self):
        self.make(image(), [("../escape", b"bad")])
        with self.assertRaises(audit.AuditError):
            audit.audit(self.path)
    def test_duplicate_entries_rejected(self):
        self.make(image(), [("Payload/Demo.app/Demo", image())])
        with self.assertRaises(audit.AuditError):
            audit.audit(self.path)
    def test_symlink_rejected(self):
        self.make(image())
        with zipfile.ZipFile(self.path, "a") as z:
            info = zipfile.ZipInfo("Payload/Demo.app/link")
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            z.writestr(info, "/etc/passwd")
        with self.assertRaises(audit.AuditError):
            audit.audit(self.path)
    def test_fat_all_architectures_checked(self):
        slices = audit.macho(fat())
        self.assertEqual(len(slices), 2)
        self.assertEqual(slices[1]["encryption"]["cryptid"], 1)
    def test_fat_overlap_rejected(self):
        data = bytearray(fat())
        struct.pack_into(">I", data, 36, 4096)
        with self.assertRaises(audit.AuditError):
            audit.macho(data)
    def test_archive_with_fat(self):
        self.make(fat())
        self.assertEqual(audit.audit(self.path)["encrypted_slice_count"], 1)
    def test_truncated_commands_rejected(self):
        data = bytearray(image())
        struct.pack_into("<I", data, 20, len(data))
        with self.assertRaises(audit.AuditError):
            audit.macho(data)
    def test_fat_table_cpu_mismatch_rejected(self):
        data = bytearray(fat())
        struct.pack_into(">I", data, 8, 7)
        with self.assertRaises(audit.AuditError):
            audit.macho(data)
    def test_malformed_encryption_command_rejected(self):
        data = bytearray(image())
        struct.pack_into("<I", data, 32, 0x21)
        with self.assertRaises(audit.AuditError):
            audit.macho(data)
    def test_member_budget_enforced(self):
        self.make(image())
        original = audit.MEMBER_LIMIT
        try:
            audit.MEMBER_LIMIT = 4096
            with self.assertRaises(audit.AuditError):
                audit.audit(self.path)
        finally:
            audit.MEMBER_LIMIT = original
    def test_invalid_plist_rejected(self):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("Payload/Demo.app/Info.plist", b"not a plist")
        with self.assertRaises(plistlib.InvalidFileException):
            audit.audit(self.path)

if __name__ == "__main__":
    unittest.main()
