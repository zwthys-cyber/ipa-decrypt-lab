"""Project uploader adapter backed by a remote durable journal, never an ephemeral upload journal."""
from pathlib import Path
import os
import sys
import time
import json
from urllib.parse import urlsplit,parse_qsl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"free-pilot"))
from private_upload import Drive,upload,validate_file,file_snapshot
from task_context import require

class RemoteJournal:
 def __init__(self,rpc,identity,checkpoint):
  self.rpc=rpc;self.identity=identity;self.checkpoint=checkpoint
 def read(self):
  self.checkpoint()
  return self.rpc("upload-journal",dict(self.identity,action="get",state=None))["state"]
 def write(self,state):
  self.checkpoint()
  try:self.rpc("upload-journal",dict(self.identity,action="put",state=state))
  except ValueError as error:
   if str(error)=="upload_session" and state.get("stage")=="uploading":
    # Shape only. Never print the resumable ID, query values, access token or Location.
    parsed=urlsplit(state["session"]);items=parse_qsl(parsed.query)
    known={"uploadType","upload_id","fields","alt","upload_protocol"}
    print(json.dumps(dict(stage="upload_session_shape",https=parsed.scheme=="https",
     google_host=parsed.hostname=="www.googleapis.com",expected_path=parsed.path=="/upload/drive/v3/files",
     query_keys=sorted(k if k in known else "other" for k,v in items),
     upload_id_length=len(dict(items).get("upload_id","")))),flush=True)
   raise

class LeasedDrive(Drive):
 def __init__(self,rpc,identity,checkpoint):
  self.rpc=rpc;self.identity=identity;self.checkpoint=checkpoint;self.renew_after=0
  value=self.renew()
  super().__init__(value["access_token"],value["recipient_email"])
 def renew(self):
  self.checkpoint()
  value=self.rpc("upload-access",self.identity)
  require(type(value.get("access_token")) is str and type(value.get("recipient_email")) is str and
   type(value.get("refresh_after")) is int and int(time.time())<value["refresh_after"]<=int(time.time())+120,"upload_access_binding")
  self.renew_after=value["refresh_after"]
  if hasattr(self,"email"):
   require(self.email==value["recipient_email"],"upload_owner_changed");self._token=value["access_token"]
  return value
 def call(self,*args,**kwargs):
  self.checkpoint()
  if int(time.time())>=self.renew_after:self.renew()
  result=super().call(*args,**kwargs)
  self.checkpoint();return result

def deliver(path,receipt,rpc,identity,origin,checkpoint=lambda:None,*,fixture=False):
 path=Path(path)
 require((not fixture and receipt.get("plaintext_verified") is True and receipt.get("account_data_removed") is True) or
  (fixture and receipt.get("schema")=="circleci-private-upload-fixture-v1" and receipt.get("fixture_authorized") is True and
   receipt.get("decryption_proven") is False and receipt.get("plaintext_verified") is False and receipt.get("archive_verified") is True),
  "upload_plaintext_proof")
 rpc("plaintext-proof",dict(identity,receipt=receipt))
 drive=LeasedDrive(rpc,identity,checkpoint);journal=RemoteJournal(rpc,identity,checkpoint)
 descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
 with os.fdopen(descriptor,"rb") as stream:
  stamp=file_snapshot(stream);record=validate_file(stream,receipt["filename"])
  require(record["bytes"]==receipt["plaintext_bytes"] and record["sha256"]==receipt["plaintext_sha256"],"upload_source_binding")
  verified,state=upload(drive,stream,record,journal,identity["job_id"],source_stamp=stamp)
  if state["stage"]=="uploaded":
   state=dict(state,stage="registration_intent",registration_origin=origin);journal.write(state)
  require(state["stage"] in ("registration_intent","registered"),"upload_registration_state")
  result=rpc("upload-register",dict(identity,record={k:verified[k] for k in ("file_id","filename","bytes","sha256")}))
  require(result.get("verified") is True,"upload_registration_unconfirmed")
  return {k:verified[k] for k in ("file_id","filename","bytes","sha256")}
