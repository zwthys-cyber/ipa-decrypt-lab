"""Exercise the actual automatic TF delivery receiver with synthetic archives, never Telegram."""
import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import struct
import sys
import unittest
from unittest.mock import Mock,patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_queue import GitHub,QueueError
RID="tf_"+"a"*32
OWNER=123456789
class TFDeliveryReceiver(unittest.TestCase):
    def plaintext(self,cryptid=0):
        stream=io.BytesIO()
        image=struct.pack("<8I",0xFEEDFACF,0x0100000C,0,2,1,24,0,0)+struct.pack("<6I",0x2C,24,4096,4096,cryptid,0)
        with zipfile.ZipFile(stream,"w") as archive:
            archive.writestr("Payload/Synthetic.app/Info.plist",plistlib.dumps({"CFBundleIdentifier":"example.synthetic",
                "CFBundleExecutable":"Synthetic","CFBundleShortVersionString":"1.0"}))
            archive.writestr("Payload/Synthetic.app/Synthetic",image.ljust(8192,b"\0"))
        return stream.getvalue()
    def run_case(self,invite="SYNTH123",profile="tf",cryptid=0):
        plain=self.plaintext(cryptid);cipher=b"age-encryption.org/v1\nSYNTHETIC_CIPHER"
        receipt=dict(schema="ipa-private-delivery-v1",status="encrypted_artifact_ready",request_id=RID,
            account_profile=profile,run_id="123",source_commit="b"*40,plaintext_verified=True,account_data_removed=True,
            plaintext_published=False,runtime_verified=False,app_id="123456",plaintext_bytes=len(plain),
            ciphertext_bytes=len(cipher),plaintext_sha256=hashlib.sha256(plain).hexdigest(),
            ciphertext_sha256=hashlib.sha256(cipher).hexdigest(),target_type="testflight",testflight_invite=invite)
        zipped=io.BytesIO()
        with zipfile.ZipFile(zipped,"w") as archive:
            archive.writestr("package.ipa.age",cipher);archive.writestr("receipt.json",json.dumps(receipt))
        raw=zipped.getvalue()
        api=GitHub("SYNTHETIC");api.find=Mock(return_value={"id":123,"head_sha":"b"*40,"status":"completed",
            "conclusion":"success","event":"workflow_dispatch","head_branch":"main",
            "path":".github/workflows/testflight-private-delivery.yml",
            "display_title":"delivery-"+RID+"-tfSYNTH123-macos-26-intel"})
        api.call=Mock(return_value={"artifacts":[{"id":1,"name":"delivery-"+RID,"expired":False,
            "size_in_bytes":len(raw),"digest":"sha256:"+hashlib.sha256(raw).hexdigest()}]})
        api.archive=Mock(side_effect=lambda identifier,path:Path(path).write_bytes(raw))
        bot=Mock(base="http://127.0.0.1:8081")
        bot.document.return_value={"message_id":7,"chat":{"id":OWNER,"type":"private"},"document":{"file_size":len(plain)}}
        def decrypt(argv,**kwargs):
            self.assertEqual(argv[1],"decrypt");Path(argv[3]).write_bytes(plain);return Mock(returncode=0)
        stages=[]
        with patch("telegram_queue.subprocess.run",side_effect=decrypt) as crypt,patch("telegram_queue.shutil.disk_usage",return_value=Mock(free=10**10)),patch("telegram_queue.app_filename",return_value="Synthetic.ipa"),patch("telegram_queue.app_thumbnail",return_value=None):
            try:result=api.deliver(RID,bot,OWNER,"SYNTHETIC_CRYPT",progress=stages.append);error=None
            except QueueError as exc:result=None;error=str(exc)
            return result,error,bot,crypt.call_count,stages,len(plain)
    def test_valid_tf_receipt_reaches_only_the_owner_after_independent_audit(self):
        result,error,bot,calls,stages,size=self.run_case()
        self.assertIsNone(error);self.assertEqual(result["status"],"telegram_file_delivered")
        self.assertEqual(result["bytes"],size);self.assertEqual(calls,1)
        self.assertEqual(stages,["retrieving","delivery_verifying","uploading"])
        self.assertEqual(bot.document.call_args.args[0]["chat_id"],OWNER)
    def test_wrong_invitation_or_account_never_decrypts_or_sends(self):
        for kwargs in ({"invite":"OTHER123"},{"profile":"cn"}):
            result,error,bot,calls,stages,size=self.run_case(**kwargs)
            self.assertIsNone(result);self.assertIsNotNone(error);self.assertEqual(calls,0);bot.document.assert_not_called()
    def test_receipt_claim_does_not_override_an_encrypted_output_image(self):
        result,error,bot,calls,stages,size=self.run_case(cryptid=1)
        self.assertIsNone(result);self.assertEqual(error,"delivery_contains_encrypted_images");bot.document.assert_not_called()
