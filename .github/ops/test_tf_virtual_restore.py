import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from tf_virtual_restore import RUN, SOURCE, unpack_private

class VirtualRestoreTests(unittest.TestCase):
    def archive(self,extra=None,source=SOURCE):
        data=io.BytesIO()
        profile={"schema":"testflight-virtual-profile-v1","origin":"independent_sdk_virtual_identity",
                 "run_id":str(RUN),"source_commit":source,"hardware20":"01"*20}
        with tarfile.open(fileobj=data,mode="w:gz") as archive:
            for name,body in (("profile.json",json.dumps(profile).encode()),("sdk/identity.json",b"SYNTHETIC")):
                item=tarfile.TarInfo(name);item.mode=0o600;item.size=len(body)
                archive.addfile(item,io.BytesIO(body))
            if extra is not None:archive.addfile(extra,io.BytesIO(b""))
        return data.getvalue()

    def test_bound_identity_is_restored_without_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            unpack_private(self.archive(),root)
            self.assertEqual(json.loads((root/"profile.json").read_text())["hardware20"],"01"*20)
            self.assertEqual((root/"sdk/identity.json").stat().st_mode&0o777,0o600)

    def test_wrong_source_and_existing_state_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with self.assertRaises(ValueError):unpack_private(self.archive(source="0"*40),root)
            (root/"existing").write_text("SYNTHETIC")
            with self.assertRaises(ValueError):unpack_private(self.archive(),root)

    def test_traversal_links_and_duplicates_are_rejected_before_writing(self):
        for name,kind in (("../outside",tarfile.REGTYPE),("sdk/link",tarfile.SYMTYPE),
                          ("profile.json",tarfile.REGTYPE),("/absolute",tarfile.REGTYPE)):
            item=tarfile.TarInfo(name);item.mode=0o600;item.type=kind;item.linkname="/outside"
            with self.subTest(name=name),tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                with self.assertRaises(ValueError):unpack_private(self.archive(item),root)
                self.assertFalse(any(root.iterdir()))
