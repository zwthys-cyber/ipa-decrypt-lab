import importlib.util
import io
import tracemalloc
from unittest.mock import patch
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
    def test_large_resource_archive_within_bounded_limit(self):
        self.make(image(), [(f"Payload/Demo.app/resources/{i}.dat",b"x") for i in range(4096)])
        self.assertEqual(audit.audit(self.path)["encrypted_slice_count"],1)

    def test_entry_limit_remains_enforced(self):
        self.make(image(), [("Payload/Demo.app/resource",b"x")])
        original=audit.ENTRY_LIMIT
        try:
            audit.ENTRY_LIMIT=2
            with self.assertRaisesRegex(audit.AuditError,"archive entry limit exceeded"):
                audit.audit(self.path)
        finally:
            audit.ENTRY_LIMIT=original

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
    def test_total_read_budget_remains_enforced(self):
        self.make(image())
        original=audit.READ_LIMIT
        try:
            audit.READ_LIMIT=4096
            with self.assertRaisesRegex(audit.AuditError,"audit read budget exceeded"):
                audit.audit(self.path)
        finally:
            audit.READ_LIMIT=original

    def test_large_member_has_bounded_python_memory(self):
        # A real member larger than the previous 512 MiB limit, constructed
        # incrementally; no large fixture or account material is committed.
        self.make()
        size=513*1024*1024
        with zipfile.ZipFile(self.path,"a",compression=zipfile.ZIP_DEFLATED,compresslevel=1) as z:
            with z.open("Payload/Demo.app/Demo","w",force_zip64=True) as writer:
                header=image()
                writer.write(header)
                remaining=size-len(header)
                block=b"\\0"*(1024*1024)
                while remaining:
                    amount=min(len(block),remaining)
                    writer.write(block[:amount])
                    remaining-=amount
        tracemalloc.start()
        try:
            result=audit.audit(self.path)
            peak=tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertEqual(result["encrypted_slice_count"],1)
        self.assertLess(peak,16*1024*1024)

    def test_stream_read_requests_bounded_and_fat_equivalent(self):
        class Bounded(io.BytesIO):
            def read(self,size=-1):
                if not 0 <= size <= audit.STREAM_CHUNK:
                    raise AssertionError("unbounded read")
                return super().read(size)
        for data in (image(),fat()):
            stream=Bounded(data)
            magic=stream.read(4)
            self.assertEqual(audit.streamed_macho(stream,magic,len(data)),audit.macho(data))

    def test_stream_truncation_and_extra_bytes_rejected(self):
        data=image()
        for payload in (data[:-1],data+b"x"):
            stream=io.BytesIO(payload)
            with self.assertRaisesRegex(audit.AuditError,"member length mismatch"):
                audit.streamed_macho(stream,stream.read(4),len(data))

    def test_scratch_is_closed_on_parse_error(self):
        scratch=tempfile.TemporaryFile()
        data=bytearray(image())
        struct.pack_into("<I",data,20,len(data))
        stream=io.BytesIO(data)
        with patch.object(audit.tempfile,"TemporaryFile",return_value=scratch):
            with self.assertRaises(audit.AuditError):
                audit.streamed_macho(stream,stream.read(4),len(data))
        self.assertTrue(scratch.closed)

    def test_large_member_crc_still_checked(self):
        self.make(image())
        with zipfile.ZipFile(self.path) as z:
            entry=z.getinfo("Payload/Demo.app/Demo")
            offset=entry.header_offset+30+len(entry.filename.encode())+len(entry.extra)
        with self.path.open("r+b") as f:
            f.seek(offset+8000)
            f.write(b"x")
        with self.assertRaises(zipfile.BadZipFile):
            audit.audit(self.path)

    def test_invalid_plist_rejected(self):
        with zipfile.ZipFile(self.path, "w") as z:
            z.writestr("Payload/Demo.app/Info.plist", b"not a plist")
        with self.assertRaises(plistlib.InvalidFileException):
            audit.audit(self.path)

if __name__ == "__main__":
    unittest.main()
