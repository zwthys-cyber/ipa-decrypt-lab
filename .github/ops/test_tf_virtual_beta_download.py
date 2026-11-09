import json
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile
from tf_virtual_beta_download import validate,archive_binding
class BetaDownloadEvidenceTests(unittest.TestCase):
    def fixture(self):
        return dict(schema="tf-beta-download-v2",status="beta_downloaded",stage="archive_received",
            downloaded=True,transport_removed=True,transport_mode="encrypted",decryption_proven=False,archive_members=2,
            encrypted_images=1,clear_images=0,downloaded_bytes=100,output_bytes=100,http_status=200,failure_category="none")
    def test_encrypted_download_cannot_claim_content_decryption(self):
        self.assertFalse(validate(self.fixture())["decryption_proven"])
        value=self.fixture();value["decryption_proven"]=True
        with self.assertRaises(ValueError):validate(value)
    def test_publisher_rejects_raw_data_wrong_types_and_missing_proofs(self):
        for key,item in (("body","PRIVATE"),("http_status",True),("output_bytes",0),("archive_members",0),("downloaded",False),("transport_removed",False)):
            value=self.fixture();value[key]=item
            with self.assertRaises(ValueError):validate(value)
    def test_archive_requires_exact_main_bundle_and_safe_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"fixture.ipa"
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("Payload/Fixture.app/Info.plist",plistlib.dumps(dict(CFBundleIdentifier="example.fixture",CFBundleExecutable="Fixture")))
                z.writestr("Payload/Fixture.app/Fixture",b"SYNTHETIC")
            self.assertEqual(archive_binding(path,"example.fixture"),2)
            with self.assertRaises(ValueError):archive_binding(path,"example.different")
            with zipfile.ZipFile(path,"a") as z:z.writestr("Payload/../PRIVATE",b"SYNTHETIC")
            with self.assertRaises(ValueError):archive_binding(path,"example.fixture")

    def test_plain_zip_is_distinct_from_removed_encryption(self):
        value=self.fixture();value.update(transport_mode="plain_zip",transport_removed=False)
        self.assertFalse(validate(value)["transport_removed"])
        value["transport_removed"]=True
        with self.assertRaises(ValueError):validate(value)
        value=self.fixture();value["transport_mode"]="unknown"
        with self.assertRaises(ValueError):validate(value)
