"""Synthetic cleanup contracts, no live network or deletion."""
import unittest
import tempfile
from pathlib import Path
import private_upload as u
import private_cleanup as c
JOB="pilot_"+"a"*32
FILE="syntheticFileID123"
OWNER="owner@example.invalid"
ORIGIN="https://pilot.example.invalid"
REC={"filename":"Example.zip","bytes":10000000000,"sha256":"b"*64}
class FakeDrive:
    email=OWNER
    def __init__(self):self.deletes=0;self.marker=True;self.fail=False
    def verify(self,record,file):
        assert record==REC and file==FILE
        return {**record,"file_id":file}
    def get(self,path):
        assert path.startswith("files/"+FILE+"?")
        return {"id":FILE,"ownedByMe":True,"trashed":False,"capabilities":{"canDelete":True},
            "appProperties":{"pilot_job":JOB,"pilot_schema":"private-link-v1"} if self.marker else {}}
    def call(self,method,url):
        assert method=="DELETE" and url==u.GOOGLE+"/drive/v3/files/"+FILE
        self.deletes+=1
        if self.fail:raise u.Stop("network_outcome_unknown")
        return 204,{},b""
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.j=u.Journal(Path(self.tmp.name),JOB)
        self.j.write({"job_id":JOB,"record":REC,"owner":OWNER,"stage":"registered","file_id":FILE,"registration_origin":ORIGIN})
        self.d=FakeDrive();self.calls=0;self.allowed=True
    def tearDown(self):self.tmp.cleanup()
    def send(self,method,url,headers,body):
        self.calls+=1
        assert method=="POST" and url==ORIGIN+"/v1/link-retire"
        assert u.decode(body)=={**REC,"job_id":JOB,"file_id":FILE}
        return (200 if self.allowed else 409),{},u.encode({"ok":self.allowed})
    def run_cleanup(self,confirm=False):
        with self.j:return c.cleanup(self.d,self.j,JOB,ORIGIN,"I"*48,confirm,self.send)
    def test_default_no_writes_and_expiry_gate(self):
        self.assertEqual(self.run_cleanup(),"cleanup_inspection_only")
        self.assertEqual((self.calls,self.d.deletes),(0,0))
        self.allowed=False
        with self.assertRaisesRegex(u.Stop,"retirement_not_confirmed"):self.run_cleanup(True)
        self.assertEqual(self.d.deletes,0)
        self.allowed=True
        self.assertEqual(self.run_cleanup(True),"private_file_deleted")
        self.assertEqual(self.run_cleanup(True),"private_file_deleted")
        self.assertEqual(self.d.deletes,1)
    def test_unmarked_file_never_deleted(self):
        self.d.marker=False
        with self.assertRaisesRegex(u.Stop,"cleanup_origin_unverified"):self.run_cleanup(True)
        self.assertEqual((self.calls,self.d.deletes),(0,0))
    def test_unknown_delete_is_not_repeated(self):
        self.d.fail=True
        with self.assertRaises(u.Stop):self.run_cleanup(True)
        self.assertEqual(self.j.read()["stage"],"delete_intent")
        with self.assertRaisesRegex(u.Stop,"do_not_repeat"):self.run_cleanup(True)
        self.assertEqual(self.d.deletes,1)
if __name__=="__main__":unittest.main()
