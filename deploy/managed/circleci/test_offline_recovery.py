"""CI-only synthetic archive/SQLite and mocked Bot API, no source access or Apple calls."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import offline_recovery as recovery
import verify_preservation
import retain_canary_archive as retained

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.owner="12345";self.scope=hashlib.sha256(("telegram-owner:"+self.owner).encode()).hexdigest()
        self.old="123456789:"+"A"*36;self.new="123456789:"+"B"*36
        self.session=b"age-encryption.org/v1\nsynthetic-session"
        self.digest=hashlib.sha256(self.session).hexdigest()
        for module in (recovery,verify_preservation):
            guard=patch.object(module,"PROMOTED",self.digest);guard.start();self.addCleanup(guard.stop)
        self.index=retained.manifest(b"synthetic")
        self.counter=0

    def snapshot(self,*,bad_digest=False,unfinished=False,foreign=False,acceptance=False):
        stage=self.root/("fixture-"+str(self.counter));self.counter+=1;stage.mkdir()
        dbpath=stage/"controller"
        with sqlite3.connect(dbpath) as db:
            db.execute("CREATE TABLE tasks(scope TEXT,rid TEXT,app TEXT,state TEXT,at INTEGER,created INTEGER)")
            db.execute("CREATE TABLE updates(scope TEXT,uid INTEGER,at INTEGER,done INTEGER)")
            db.execute("CREATE TABLE metadata(scope TEXT,name TEXT,value TEXT)")
            db.executemany("INSERT INTO tasks VALUES(?,?,?,?,?,?)",[
                (self.scope,"a"*32,"123456","delivered",110,100),
                ("f"*64 if foreign else self.scope,"cn_"+"b"*32,"654321","pending",120,115)])
            db.execute("INSERT INTO updates VALUES(?,?,?,?)",(self.scope,100,120,int(not unfinished)))
            db.executemany("INSERT INTO metadata VALUES(?,?,?)",[
                (self.scope,"offset","101"),(self.scope,"version_browser",json.dumps(dict(view={"closed":True})))])
        returns=stage/"returns"
        with sqlite3.connect(returns) as db:
            db.execute("CREATE TABLE deliveries(request_id TEXT,state TEXT)")
            db.execute("INSERT INTO deliveries VALUES('synthetic-private-return','confirmed')")
        records={"state/state.sqlite3":dbpath.read_bytes(),"state/tf-private-return.sqlite":returns.read_bytes(),
            "state/testflight/session.age":self.session,"state/telegram/session.bin":b"synthetic-opaque-session",
            "config/bot.json":json.dumps(dict(TELEGRAM_OWNER_ID=self.owner,TELEGRAM_BOT_TOKEN=self.old,
                DELIVERY_AGE_IDENTITY="must-not-appear-in-plan")).encode()}
        if acceptance:
            path=stage/"acceptance"
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE invitations(invite TEXT,request_id TEXT,run_id TEXT,source_commit TEXT,nonce TEXT,expires INTEGER,state TEXT)")
                db.execute("INSERT INTO invitations VALUES('SyntheticInvite','tf_x','123',?,'',0,'outcome_unknown')",("a"*40,))
            records["state/testflight/acceptance.sqlite"]=path.read_bytes()
        files={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in records.items()}
        if bad_digest:files["state/state.sqlite3"]["sha256"]="0"*64
        records["manifest.json"]=json.dumps(dict(schema="ipa-online-preservation-v1",frozen=True,cutover_approved=False,
            captured_at=130,session_sha256=self.digest,files=files,task_states=dict(delivered=1,pending=1),
            bounded_pause=dict(source_sha=retained.SOURCE,run_id=str(retained.RUN),paused_at=129,expires_at=1000))).encode()
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode="w:gz") as archive:
            for name,raw in records.items():
                member=tarfile.TarInfo(name);member.size=len(raw);archive.addfile(member,io.BytesIO(raw))
        return output.getvalue()

    def plan(self,**kwargs):
        root=self.root/("read-"+str(self.counter));root.mkdir()
        return recovery.plan(self.snapshot(**kwargs),root,self.owner,self.index,now=2000)

    def test_verified_snapshot_preserves_records_and_never_grants_cutover(self):
        value,proof=self.plan(foreign=True)
        self.assertEqual(proof["legacy_rows"],2);self.assertEqual(proof["held_rows"],1)
        self.assertTrue(proof["owner_offset_preserved"]);self.assertTrue(proof["owner_browser_preserved"])
        self.assertEqual(value["source_snapshot_offset"],101);self.assertIsNone(value["new_update_floor"])
        self.assertTrue(value["recovery_gap_unresolved"]);self.assertFalse(value["permanent_handoff"])
        self.assertFalse(value["source_currently_frozen"]);self.assertFalse(value["automatic_replay"])
        self.assertTrue(value["requires_historical_tf_reconstruction"])
        self.assertEqual(value["records"]["legacy_tasks"][1]["owner_id"],"legacy:"+"f"*64)
        text=json.dumps(value)
        self.assertNotIn(self.old,text);self.assertNotIn("must-not-appear-in-plan",text)

    def test_manifest_tamper_or_wrong_owner_fails_without_usable_plan(self):
        with self.assertRaises(ValueError):self.plan(bad_digest=True)
        root=self.root/"wrong-owner";root.mkdir()
        with self.assertRaises(ValueError):recovery.plan(self.snapshot(),root,"99999",self.index,now=2000)

    def test_unfinished_updates_are_preserved_and_never_replayed(self):
        value,proof=self.plan(unfinished=True)
        self.assertEqual(proof["unfinished_updates"],1)
        self.assertEqual(value["records"]["updates"][0]["done"],0)
        self.assertFalse(value["automatic_replay"])

    def test_existing_unknown_acceptance_is_preserved_without_initialization(self):
        value,proof=self.plan(acceptance=True)
        self.assertTrue(proof["acceptance_ledger_present"]);self.assertEqual(proof["acceptance_rows"],1)
        self.assertFalse(value["requires_historical_tf_reconstruction"])
        self.assertEqual(value["records"]["acceptance_rows"][0]["state"],"outcome_unknown")

    def transport(self,old_code=401,new_id=123456789):
        class Reply(io.BytesIO):
            def __init__(self,code,value):
                super().__init__(json.dumps(value).encode());self.status=code
        def execute(request,timeout):
            self.assertEqual(timeout,15)
            self.assertTrue(request.full_url.startswith("https://api.telegram.org/bot"))
            self.assertTrue(request.full_url.endswith("/getMe"))
            if self.new in request.full_url:
                return Reply(200,dict(ok=True,result=dict(id=new_id,is_bot=True)))
            return Reply(old_code,dict(ok=False,error_code=old_code))
        return execute

    def test_token_replacement_proves_same_bot_and_explicit_old_rejection_only(self):
        proof=recovery.verify_replacement(self.old,self.new,self.transport())
        self.assertTrue(proof["old_token_rejected"]);self.assertTrue(proof["replacement_same_bot_verified"])
        self.assertNotIn(self.new,json.dumps(proof))
        self.assertNotIn("telegram_isolation_verified",proof)

    def test_same_token_wrong_bot_or_transient_error_cannot_prove_fencing(self):
        for old,new,transport in [(self.old,self.old,self.transport()),(self.old,self.new,self.transport(new_id=987654321)),
                                  (self.old,self.new,self.transport(old_code=429)),(self.old,self.new,self.transport(old_code=500))]:
            with self.assertRaises(ValueError):recovery.verify_replacement(old,new,transport)
        with self.assertRaises(ValueError):recovery.verify_replacement(self.old,"987654321:"+"C"*36,self.transport())

if __name__=="__main__":unittest.main()
