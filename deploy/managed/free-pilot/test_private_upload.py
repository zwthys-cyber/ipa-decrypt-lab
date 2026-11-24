"""Synthetic fake HTTP tests; never use Google, Telegram, or production credentials."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import private_upload as u

JOB="pilot_"+"a"*32
SESSION=u.GOOGLE+"/upload/drive/v3/files?uploadType=resumable&upload_id=synthetic"
FILE="syntheticFileID123"
EMAIL="owner@example.invalid"
TOKEN="synthetic-access-token-123456789"
ORIGIN="https://pilot.example.invalid"
class Fake:
    def __init__(self,record):
        self.record=record
        self.offset=0;self.starts=0;self.interrupt=False;self.bad_hash=False
        self.full=False;self.share=False;self.register_calls=0
    def reply(self,value,status=200):return status,{},u.encode(value)
    def __call__(self,method,url,headers,body):
        if "/about?" in url:
            return self.reply({"user":{"emailAddress":EMAIL},"storageQuota":{"limit":str(u.FREE_LIMIT),"usage":str(u.FREE_LIMIT if self.full else 0)}})
        if method=="POST" and url.startswith(u.GOOGLE+"/upload/"):
            self.starts+=1
            return 200,{"location":SESSION},b""
        if method=="PUT" and url==SESSION:
            if headers["Content-Range"].startswith("bytes */"):
                if self.offset==self.record["bytes"]:return self.reply({"id":FILE})
                return 308,{"range":f"bytes=0-{self.offset-1}"} if self.offset else {},b""
            start=self.offset
            assert headers["Content-Range"]==f"bytes {start}-{start+len(body)-1}/{self.record['bytes']}"
            self.offset+=len(body)
            if self.interrupt:
                self.interrupt=False
                raise u.Stop("network_outcome_unknown")
            if self.offset==self.record["bytes"]:return self.reply({"id":FILE},201)
            return 308,{"range":f"bytes=0-{self.offset-1}"},b""
        if "/permissions?" in url:
            p=[{"type":"user","role":"owner","emailAddress":EMAIL}]
            if self.share:p.append({"type":"anyone","role":"reader"})
            return self.reply({"permissions":p})
        if url.startswith(u.GOOGLE+"/drive/v3/files/"+FILE+"?"):
            return self.reply({"id":FILE,"name":self.record["filename"],"size":str(self.record["bytes"]),
                "sha256Checksum":"0"*64 if self.bad_hash else self.record["sha256"],"trashed":False,
                "ownedByMe":True,"mimeType":"application/octet-stream"})
        if method=="POST" and url==ORIGIN+"/v1/link-register":
            self.register_calls+=1
            assert headers["Authorization"]=="Bearer "+"I"*48
            assert json.loads(body)["job_id"]==JOB
            return self.reply({"ok":True},201)
        raise AssertionError("unexpected transport")

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.file=self.root/"Example.bin"
        self.file.write_bytes(b"a"*(256*1024)+b"b"*33)
        self.file.chmod(0o600)
        self.stream=self.file.open("rb")
        self.record=u.validate_file(self.stream,self.file.name)
        self.fake=Fake(self.record)
        self.drive=u.Drive(TOKEN,EMAIL,self.fake)
        self.journal=u.Journal(self.root/"journal",JOB)
    def tearDown(self):self.stream.close();self.tmp.cleanup()
    def run_upload(self):
        with self.journal:
            return u.upload(self.drive,self.stream,self.record,self.journal,JOB)
    def test_upload_interruption_and_registration(self):
        self.fake.interrupt=True
        with patch.object(u,"CHUNK",256*1024):
            with self.assertRaises(u.Stop):self.run_upload()
            self.assertEqual(self.fake.offset,256*1024)
            receipt,state=self.run_upload()
            self.assertEqual(self.fake.starts,1)
            self.assertEqual(receipt["sha256"],self.record["sha256"])
            with self.journal:
                u.register(receipt,state,self.journal,ORIGIN,"I"*48,self.fake)
                u.register(receipt,self.journal.read(),self.journal,ORIGIN,"I"*48,self.fake)
            self.assertEqual(self.fake.register_calls,1)
    def test_free_capacity_guard(self):
        self.fake.full=True
        with self.assertRaisesRegex(u.Stop,"free_storage_insufficient"):self.run_upload()
        self.assertEqual(self.fake.starts,0)
        self.assertIsNone(self.journal.read())
    def test_bad_hash_and_public_acl(self):
        self.fake.bad_hash=True
        with self.assertRaisesRegex(u.Stop,"file_integrity_unverified"):self.run_upload()
        self.fake.bad_hash=False;self.fake.share=True
        with self.assertRaisesRegex(u.Stop,"file_not_owner_only"):self.run_upload()
        self.assertEqual(self.fake.starts,1)
    def test_start_unknown_never_recreated(self):
        self.journal.write({"job_id":JOB,"record":self.record,"owner":EMAIL,"stage":"start_intent"})
        with self.assertRaisesRegex(u.Stop,"do_not_recreate"):self.run_upload()
        self.assertEqual(self.fake.starts,0)
    def test_registration_unknown_not_retried(self):
        receipt,state=self.run_upload()
        def fail(*args):raise u.Stop("network_outcome_unknown")
        with self.journal:
            with self.assertRaises(u.Stop):u.register(receipt,state,self.journal,ORIGIN,"I"*48,fail)
            with self.assertRaisesRegex(u.Stop,"check_database"):u.register(receipt,self.journal.read(),self.journal,ORIGIN,"I"*48,self.fake)
        self.assertEqual(self.fake.register_calls,0)
    def test_invalid_session_and_quota(self):
        for url in ("http://www.googleapis.com/upload/drive/v3/files?upload_id=x","https://evil.invalid/upload/drive/v3/files?upload_id=x"):
            with self.assertRaises(u.Stop):u.session_url(url)
        with self.assertRaises(u.Stop):u.quota({"user":{"emailAddress":EMAIL},"storageQuota":{"limit":str(u.FREE_LIMIT+1),"usage":"0"}},EMAIL,1)
    def test_10gb_quota_boundary(self):
        self.assertEqual(u.MAX,10_000_000_000)
        exact=u.FREE_LIMIT-u.MAX-u.RESERVE
        value={"user":{"emailAddress":EMAIL},"storageQuota":{"limit":str(u.FREE_LIMIT),"usage":str(exact)}}
        u.quota(value,EMAIL,u.MAX)
        value["storageQuota"]["usage"]=str(exact+1)
        with self.assertRaisesRegex(u.Stop,"free_storage_insufficient"):u.quota(value,EMAIL,u.MAX)
        value["storageQuota"]["usage"]="0"
        for size in (0,1.5,u.MAX+1):
            with self.assertRaisesRegex(u.Stop,"file_size_out_of_bounds"):u.quota(value,EMAIL,size)
    def test_large_resume_offsets_and_last_chunk(self):
        # No multi-GB allocation or upload. Model a stream at two large offsets.
        class VirtualStream:
            def seek(self,position):self.position=position
            def read(self,count):
                assert 0<count<=u.CHUNK
                return b"x"*count
        record={"filename":"Synthetic.bin","bytes":u.MAX,"sha256":"a"*64}
        fake=Fake(record);drive=u.Drive(TOKEN,EMAIL,fake);stream=VirtualStream()
        fake.offset=2**32
        offset,file_id=drive.resume(SESSION,u.MAX)
        self.assertEqual(offset,2**32);self.assertIsNone(file_id)
        offset,file_id=drive.chunk(SESSION,stream,offset,u.MAX)
        self.assertEqual(offset,2**32+u.CHUNK);self.assertIsNone(file_id)
        fake.offset=(u.MAX//u.CHUNK)*u.CHUNK
        offset,file_id=drive.resume(SESSION,u.MAX)
        self.assertEqual(offset,fake.offset)
        offset,file_id=drive.chunk(SESSION,stream,offset,u.MAX)
        self.assertIsNone(offset);self.assertEqual(file_id,FILE)
        self.assertEqual(fake.offset,u.MAX)
        self.assertEqual(drive.verify(record,FILE)["bytes"],u.MAX)
    def test_resume_stops_if_free_capacity_changes(self):
        self.fake.interrupt=True
        with patch.object(u,"CHUNK",256*1024):
            with self.assertRaises(u.Stop):self.run_upload()
            before=self.fake.offset
            self.fake.full=True
            with self.assertRaisesRegex(u.Stop,"free_storage_insufficient"):self.run_upload()
            self.assertEqual(self.fake.offset,before)
            self.assertEqual(self.fake.starts,1)

class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.now=100
        self.calls=[]
        self.env={"PILOT_DRIVE_CLIENT_ID":"synthetic-client-123.apps.googleusercontent.com",
                  "PILOT_DRIVE_CLIENT_SECRET":"synthetic-client-secret","PILOT_DRIVE_REFRESH_TOKEN":"synthetic-refresh-token",
                  "PILOT_DRIVE_RECIPIENT_EMAIL":EMAIL,"PILOT_DRIVE_ACCESS_TOKEN":TOKEN}
        self.response={"access_token":"synthetic-fresh-access-token","token_type":"Bearer","expires_in":3600,"scope":u.SCOPE}
        self.status=200
    def send(self,method,url,headers,body):
        self.calls.append((method,url))
        if url==u.OAUTH_URL:
            self.assertEqual(method,"POST")
            self.assertNotIn("Authorization",headers)
            self.assertEqual(headers["Content-Type"],"application/x-www-form-urlencoded")
            self.assertIn(b"grant_type=refresh_token",body)
            return self.status,{},u.encode(self.response)
        self.assertEqual(headers["Authorization"],"Bearer synthetic-fresh-access-token")
        return 200,{},u.encode({})
    def drive(self):return u.Drive.from_env(self.env,self.send,lambda:self.now)
    def test_refresh_reuses_token_until_safety_margin(self):
        d=self.drive();d.get("about");self.now=3639;d.get("about")
        self.assertEqual(sum(url==u.OAUTH_URL for _,url in self.calls),1)
        self.now=3640;d.get("about")
        self.assertEqual(sum(url==u.OAUTH_URL for _,url in self.calls),2)
    def test_invalid_grant_latches_and_no_manual_fallback(self):
        self.status=400;self.response={"error":"invalid_grant"}
        d=self.drive()
        for _ in range(2):
            with self.assertRaisesRegex(u.Stop,"drive_reauthorization_required"):d.get("about")
        self.assertEqual(self.calls,[("POST",u.OAUTH_URL)])
    def test_partial_configuration_fails_before_network(self):
        del self.env["PILOT_DRIVE_REFRESH_TOKEN"]
        with self.assertRaisesRegex(u.Stop,"invalid_drive_credentials"):self.drive()
        self.assertEqual(self.calls,[])
    def test_reject_redirect_wrong_scope_short_lifetime_and_rotation(self):
        original=self.response.copy()
        for changes,status in [({},302),({"scope":"https://www.googleapis.com/auth/drive"},200),
            ({"expires_in":True},200),({"expires_in":60},200),({"refresh_token":"unexpected"},200),
            ({"scope":None},200)]:
            self.status=status;self.response={**original,**changes}
            with self.assertRaises(u.Stop):self.drive().get("about")
        self.assertTrue(all(url==u.OAUTH_URL for _,url in self.calls))
    def test_untrusted_origin_rejected_before_refresh(self):
        d=self.drive()
        with self.assertRaisesRegex(u.Stop,"invalid_drive_endpoint"):d.call("GET","https://example.invalid/drive/v3/files")
        self.assertEqual(self.calls,[])
    def test_401_on_write_does_not_repeat(self):
        calls=[]
        def send(method,url,headers,body):
            calls.append((method,url))
            if url==u.OAUTH_URL:return 200,{},u.encode(self.response)
            return 401,{},b"{}"
        d=u.Drive.from_env(self.env,send,lambda:self.now)
        with self.assertRaisesRegex(u.Stop,"upload_start_unconfirmed"):
            d.start({"filename":"Example.bin","bytes":1},JOB)
        self.assertEqual(len(calls),2)

if __name__=="__main__":unittest.main()
