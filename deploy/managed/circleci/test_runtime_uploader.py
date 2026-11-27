"""CI only: real ZIP verification with a synthetic Drive transport and remote journal."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
import runtime_uploader as worker
from private_upload import Stop

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/"fixture.ipa"
  with zipfile.ZipFile(self.path,"w") as z:
   z.writestr("Payload/Fixture.app/Info.plist",b"fixture")
   z.writestr("Payload/Fixture.app/resource",b"project-owned-synthetic")
  self.path.chmod(0o600)
  self.record=dict(filename="Fixture.ipa",bytes=self.path.stat().st_size,sha256=hashlib.sha256(self.path.read_bytes()).hexdigest())
  self.receipt=dict(plaintext_verified=True,account_data_removed=True,filename=self.record["filename"],
   plaintext_bytes=self.record["bytes"],plaintext_sha256=self.record["sha256"])
  self.state=None;self.calls=[];self.starts=0;self.fail_start=False;self.fail_register=False;self.cancel=False
  self.identity=dict(job_id="pilot_"+"a"*32,worker_job_id="12345678-1234-1234-1234-123456789abc")
  suite=self
  class FakeDrive:
   email="fixture@example.invalid"
   def __init__(self,*args):pass
   def check_quota(self,size):suite.calls.append("quota")
   def start(self,record,job):
    suite.starts+=1
    if suite.fail_start:raise Stop("network_outcome_unknown")
    return "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=SYNTHETIC_123456"
   def resume(self,session,size):return 0,None
   def chunk(self,session,stream,offset,size,check):
    check()
    if suite.cancel:raise InterruptedError()
    return size,"SYNTHETIC_FILE_12345"
   def verify(self,record,file_id):return dict(record,file_id=file_id)
  self.drive=FakeDrive
 def rpc(self,path,value):
  self.calls.append(path)
  if path=="plaintext-proof":return dict(ok=True)
  if path=="upload-journal":
   if value["action"]=="get":return dict(state=self.state)
   self.state=value["state"];return dict(ok=True)
  if path=="upload-register":
   if self.fail_register:raise TimeoutError()
   self.state=dict(self.state,stage="registered");return dict(verified=True)
  raise AssertionError(path)
 def deliver(self):
  with patch.object(worker,"LeasedDrive",self.drive):
   return worker.deliver(self.path,self.receipt,self.rpc,self.identity,"https://fixture.invalid")
 def test_complete_file_then_durable_registration(self):
  result=self.deliver();self.assertEqual(result["sha256"],self.record["sha256"])
  self.assertEqual(self.state["stage"],"registered");self.assertEqual(self.starts,1)
  self.deliver();self.assertEqual(self.starts,1)
 def test_unknown_creation_never_creates_again(self):
  self.fail_start=True
  with self.assertRaises(Stop):self.deliver()
  self.assertEqual(self.state["stage"],"start_intent")
  self.fail_start=False
  with self.assertRaisesRegex(Stop,"do_not_recreate"):self.deliver()
  self.assertEqual(self.starts,1)
 def test_lost_registration_ack_resumes_same_file(self):
  self.fail_register=True
  with self.assertRaises(TimeoutError):self.deliver()
  self.assertEqual(self.state["stage"],"registration_intent")
  self.fail_register=False;self.deliver();self.assertEqual(self.starts,1)
 def test_cancel_keeps_session_without_upload_recreation(self):
  self.cancel=True
  with self.assertRaises(InterruptedError):self.deliver()
  self.assertEqual(self.state["stage"],"uploading")
  self.cancel=False;self.deliver();self.assertEqual(self.starts,1)
 def test_mismatched_input_stops_before_drive_creation(self):
  self.receipt["plaintext_sha256"]="0"*64
  with self.assertRaisesRegex(ValueError,"source_binding"):self.deliver()
  self.assertEqual(self.starts,0);self.assertIsNone(self.state)
 def test_symlink_and_private_permissions_rejected(self):
  self.path.chmod(0o644)
  with self.assertRaises(Stop):self.deliver()
  self.path.chmod(0o600)
  target=self.path;self.path=target.with_name("link.ipa");self.path.symlink_to(target)
  with self.assertRaises(OSError):self.deliver()
  self.assertEqual(self.starts,0)
if __name__=="__main__":unittest.main()
