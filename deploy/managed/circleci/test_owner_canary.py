"""CI-only frozen-snapshot/caller tests; no SSH, systemd or Apple transport."""
import ast,hashlib,io,json,sqlite3,tarfile,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import owner_canary as worker
import pause_source
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.index=0;self.now=int(time.time())
  self.env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY="zwthys-cyber/ipa-decrypt-lab",
   GITHUB_REF="refs/heads/upgrade/managed-runtime-v0.2",GITHUB_RUN_ATTEMPT="1",GITHUB_EVENT_NAME="workflow_dispatch",
   GITHUB_ACTOR_ID="246379322",GITHUB_SHA="a"*40,GITHUB_RUN_ID="123456",RUNTIME_OWNER_ID="12345")
  self.nonce="b"*32
 def archive(self,frozen=True,owner="12345",unfinished=False):
  database=self.root/"fixture.sqlite";database.unlink(missing_ok=True)
  scope=hashlib.sha256(("telegram-owner:"+owner).encode()).hexdigest()
  with sqlite3.connect(database) as db:
   db.executescript("CREATE TABLE tasks(scope,rid,app,state,at,created);CREATE TABLE updates(scope,uid,at,done);CREATE TABLE metadata(scope,name,value);")
   db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?)",(scope,"c"*32,"123456","pending",self.now,self.now))
   db.execute("INSERT INTO metadata VALUES(?,?,?)",(scope,"offset","101"))
   if unfinished:db.execute("INSERT INTO updates VALUES(?,?,?,?)",(scope,100,self.now,0))
  session=b"age-encryption.org/v1\nsynthetic-private-carrier"
  records={"state/state.sqlite3":database.read_bytes(),"config/bot.json":json.dumps({"TELEGRAM_OWNER_ID":owner,"TELEGRAM_BOT_TOKEN":"synthetic-private-token"}).encode(),"state/testflight/session.age":session}
  digest=hashlib.sha256(session).hexdigest()
  manifest=dict(schema="ipa-online-preservation-v1",frozen=frozen,cutover_approved=False,session_sha256=digest,task_states={"pending":1},
   files={name:dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()) for name,raw in records.items()},
   bounded_pause=dict(nonce=self.nonce,source_sha=self.env["GITHUB_SHA"],run_id=self.env["GITHUB_RUN_ID"],paused_at=self.now-5,expires_at=self.now+600))
  records["manifest.json"]=json.dumps(manifest).encode();out=io.BytesIO()
  with tarfile.open(fileobj=out,mode="w:gz") as archive:
   for name,raw in records.items():
    item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o600;archive.addfile(item,io.BytesIO(raw))
  return out.getvalue(),digest
 def packet(self,compressed,digest):
  self.index+=1;root=self.root/("restore-"+str(self.index));root.mkdir()
  with patch("verify_preservation.PROMOTED",digest),patch.object(worker,"PROMOTED",digest):
   return worker.snapshot_packet(compressed,root,self.env,self.nonce,"6739782103","d"*64)
 def test_frozen_snapshot_preserves_pending_rows_and_consumed_update_floor(self):
  compressed,digest=self.archive();packet,bot=self.packet(compressed,digest)
  self.assertEqual(packet["telegram_update_floor"],101)
  self.assertEqual(packet["legacy"][0]["held"],1);self.assertEqual(packet["legacy"][0]["state"],"pending")
  self.assertEqual(packet["legacy"][0]["owner_id"],"12345");self.assertEqual(packet["target"],"6739782103")
  self.assertEqual(bot,"synthetic-private-token")
  self.assertEqual(packet["rows_sha256"],hashlib.sha256(json.dumps(packet["legacy"],separators=(",",":"),ensure_ascii=False).encode()).hexdigest())
 def test_online_snapshots_and_unfinished_updates_cannot_authorize_real_work(self):
  compressed,digest=self.archive(frozen=False)
  with self.assertRaises(ValueError):self.packet(compressed,digest)
  compressed,digest=self.archive(unfinished=True)
  with self.assertRaisesRegex(ValueError,"unfinished_updates"):self.packet(compressed,digest)
 def test_foreign_owner_snapshot_cannot_supply_bot_credentials(self):
  compressed,digest=self.archive(owner="54321")
  with self.assertRaisesRegex(ValueError,"owner_mismatch"):self.packet(compressed,digest)
 def test_only_owner_first_attempt_dispatch_may_pause_source(self):
  worker.context(self.env)
  for key,value in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_EVENT_NAME","push"),("GITHUB_ACTOR_ID","99999"),("GITHUB_ACTIONS","")):
   with self.assertRaises(ValueError):worker.context(dict(self.env,**{key:value}))
 def test_public_runtime_bootstrap_is_digest_bound_and_contains_no_credentials(self):
  raw=worker.build_transport(self.root)
  program=worker.bootstrap(raw,self.nonce,self.env["GITHUB_SHA"],self.env["GITHUB_RUN_ID"]);ast.parse(program.decode())
  self.assertIn(hashlib.sha256(raw).hexdigest().encode(),program);self.assertNotIn(b"synthetic-private-token",program)
  pause_source.bindings(self.nonce,self.env["GITHUB_SHA"],self.env["GITHUB_RUN_ID"])
  with self.assertRaises(ValueError):pause_source.bindings("../../unsafe",self.env["GITHUB_SHA"],"1")
 def test_restore_rejects_different_pause_marker_before_starting_service(self):
  marker=self.root/"marker.json";marker.write_text(json.dumps(dict(nonce="c"*32,source_sha=self.env["GITHUB_SHA"],run_id=self.env["GITHUB_RUN_ID"])));marker.chmod(0o600)
  expected=pause_source.bindings(self.nonce,self.env["GITHUB_SHA"],self.env["GITHUB_RUN_ID"])
  with patch.object(pause_source,"marker_path",return_value=marker),patch.object(pause_source,"command") as execute:
   with self.assertRaises(ValueError):pause_source.restore(expected)
   execute.assert_not_called()
if __name__=="__main__":unittest.main()
