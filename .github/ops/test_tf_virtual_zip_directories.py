import tempfile
import unittest
import zipfile
from pathlib import Path
from tf_virtual_zip_directories import canonicalize,inventory
class EmptyDirectoryCompatibility(unittest.TestCase):
    def test_deflated_directory_becomes_stored_without_any_payload_change(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"source.zip";target=Path(folder)/"canonical.zip"
            with zipfile.ZipFile(source,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("Payload/",b"")
                archive.writestr("Payload/Synthetic.app/",b"")
                archive.writestr("Payload/Synthetic.app/Synthetic",b"SYNTHETIC_PRIVATE_BYTES"*100)
            before=inventory(source);result=canonicalize(source,target)
            self.assertEqual(result,{"empty_directories_canonicalized":2,"payloads_unchanged":True,"member_count":3})
            self.assertEqual(inventory(target),before)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.getinfo("Payload/").compress_size,0)
                self.assertEqual(archive.testzip(),None)
    def test_directory_with_hidden_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/"source.zip";target=Path(folder)/"canonical.zip"
            with zipfile.ZipFile(source,"w") as archive:archive.writestr("Payload/",b"SYNTHETIC_HIDDEN_PAYLOAD")
            with self.assertRaises(ValueError):canonicalize(source,target)
