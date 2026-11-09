import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tf_return_sender import claim,receipt_valid,verify_plain,RUN,SOURCE,REQUEST
from tf_return_transport import parse
class FixedPrivateReturn(unittest.TestCase):
    def fixture(self):
        return dict(schema="ipa-private-delivery-v1",status="encrypted_artifact_ready",request_id=REQUEST,
            run_id=str(RUN),source_commit=SOURCE,account_profile="cn",plaintext_verified=True,
            account_data_removed=True,plaintext_published=False,runtime_verified=False,
            encrypted_images=1,decrypted_pages=148,plaintext_bytes=1,ciphertext_bytes=2,
            plaintext_sha256="a"*64,ciphertext_sha256="b"*64)
    def test_receipt_requires_exact_provenance_and_complete_plaintext(self):
        receipt_valid(self.fixture())
        for key,value in (("run_id","1"),("source_commit","a"*40),("request_id","other"),("plaintext_verified",False),
                ("account_data_removed",False),("account_profile","default"),("decrypted_pages",0)):
            item=self.fixture();item[key]=value
            with self.assertRaises(ValueError):receipt_valid(item)
    def test_committed_intent_survives_restart_and_blocks_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"journal.sqlite";db=sqlite3.connect(path)
            db.execute("CREATE TABLE deliveries(request TEXT PRIMARY KEY,state TEXT NOT NULL)")
            self.assertTrue(claim(db));db.close();db=sqlite3.connect(path)
            self.assertFalse(claim(db))
            self.assertEqual(db.execute("SELECT state FROM deliveries").fetchone(),("intent",));db.close()
    def test_independent_archive_rejects_encrypted_image_and_account_member(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"synthetic.ipa"
            with zipfile.ZipFile(path,"w") as z:z.writestr("Payload/Synthetic.app/Synthetic",b"SYNTHETIC")
            receipt={"plaintext_bytes":path.stat().st_size,"plaintext_sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
            with patch("tf_return_sender.audit",return_value={"encrypted_slice_count":1}):
                with self.assertRaises(ValueError):verify_plain(path,receipt)
            with zipfile.ZipFile(path,"a") as z:z.writestr("Payload/Synthetic.app/SC_Info/Synthetic.sinf",b"SYNTHETIC")
            receipt.update(plaintext_bytes=path.stat().st_size,plaintext_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            with patch("tf_return_sender.audit",return_value={"encrypted_slice_count":0}):
                with self.assertRaises(ValueError):verify_plain(path,receipt)
    def test_remote_raw_fields_and_false_ack_never_escape(self):
        good={"schema":"tf-private-return-v1","input_run":str(RUN),"status":"telegram_file_delivered","delivered":True,"bytes":100}
        self.assertTrue(parse(json.dumps(good).encode())["delivered"])
        bad=dict(good,raw="PRIVATE")
        with self.assertRaises(ValueError):parse(json.dumps(bad).encode())
        bad=dict(good,status="send_outcome_unknown")
        with self.assertRaises(ValueError):parse(json.dumps(bad).encode())
