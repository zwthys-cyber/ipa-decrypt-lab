"""CI-only synthetic ZIP64 structures; no real app or external upload."""
import io
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zip_preflight as z
import private_upload as u

def small(name="Payload/Synthetic.app/resource.bin",data=b"test"):
    f=io.BytesIO()
    with zipfile.ZipFile(f,"w") as archive:archive.writestr(name,data)
    f.seek(0);return f

class ArchiveTests(unittest.TestCase):
    def test_regular_zip_is_metadata_only(self):
        f=small();r=z.inspect(f)
        self.assertEqual(r["entries"],1)
        self.assertEqual(r["declared_expanded_bytes"],4)
        self.assertFalse(r["whole_archive_crc_verified"])
        self.assertEqual(f.tell(),0)
    def test_invalid_path_duplicate_and_limits(self):
        with self.assertRaises(z.ArchiveError):z.inspect(small("../unsafe"))
        f=small()
        with zipfile.ZipFile(f,"a") as archive:archive.writestr("Payload/Synthetic.app/resource.bin",b"other")
        with self.assertRaises(z.ArchiveError):z.inspect(f)
        with patch.object(z,"MAX_EXPANDED",3):
            with self.assertRaises(z.ArchiveError):z.inspect(small())
        with patch.object(z,"MAX_DIRECTORY",32):
            with self.assertRaises(z.ArchiveError):z.inspect(small())
    def test_truncated_and_forged_directory(self):
        raw=small().getvalue()
        for data in (raw[:-1],raw+b"x"):
            with self.assertRaises(z.ArchiveError):z.inspect(io.BytesIO(data))
        changed=bytearray(raw)
        end=changed.rfind(b"PK\x05\x06")
        struct.pack_into("<I",changed,end+12,0x7fffffff)
        with self.assertRaises(z.ArchiveError):z.inspect(io.BytesIO(changed))
    def test_sparse_zip64_with_real_offsets_over_4gib(self):
        # ZIP_STORED calculates the real CRC. A sparse sink skips writing known
        # zero blocks physically, while retaining their logical file offsets.
        block=b"\0"*(8*1024**2)
        class SparseSink:
            def __init__(self,stream):self.stream=stream
            def tell(self):return self.stream.tell()
            def seek(self,*args):return self.stream.seek(*args)
            def flush(self):return self.stream.flush()
            def write(self,data):
                if len(data)==len(block) and data==block:
                    self.stream.seek(len(data),os.SEEK_CUR);return len(data)
                return self.stream.write(data)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"synthetic.zip"
            with path.open("w+b") as f:
                with zipfile.ZipFile(SparseSink(f),"w",compression=zipfile.ZIP_STORED,allowZip64=True) as archive:
                    with archive.open("Payload/Synthetic.app/zeros.bin","w",force_zip64=True) as member:
                        for _ in range(512):member.write(block)
                        member.write(b"\0"*32)
                    archive.writestr("Payload/Synthetic.app/tail.txt",b"marker")
                f.flush()
                self.assertGreater(path.stat().st_size,2**32)
                self.assertLess(path.stat().st_blocks*512,1024*1024)
                report=z.inspect(f)
                self.assertTrue(report["zip64"])
                self.assertEqual(report["declared_expanded_bytes"],2**32+32+6)
                self.assertFalse(report["whole_archive_crc_verified"])
                with zipfile.ZipFile(f) as archive:
                    self.assertGreater(archive.getinfo("Payload/Synthetic.app/tail.txt").header_offset,2**32)
                    self.assertEqual(archive.read("Payload/Synthetic.app/tail.txt"),b"marker")
    def test_uploader_checks_archive_metadata_before_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"Example.zip"
            path.write_bytes(b"not a zip");path.chmod(0o600)
            with path.open("rb") as stream:
                with self.assertRaisesRegex(u.Stop,"archive_preflight_failed"):u.validate_file(stream,path.name)
            path.write_bytes(small().getvalue())
            with path.open("rb") as stream:
                record=u.validate_file(stream,path.name)
                self.assertEqual(record["bytes"],path.stat().st_size)
if __name__=="__main__":unittest.main()
