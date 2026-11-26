"""Synthetic frozen state comparison; no production state or credentials."""
import os
import json
import subprocess
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from managed_migration import compare, inspect_source
from testflight_state import connect, claim, finish

class ManagedMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/"source";self.controller=self.root/"controller";self.state=self.root/"state"
        for p in (self.source,self.controller,self.state,self.source/"testflight",self.source/"telegram"):
            p.mkdir(mode=0o700)
        for name,sql in (
          ("state.sqlite3","CREATE TABLE tasks(state TEXT); INSERT INTO tasks VALUES ('delivered')"),
          ("tf-private-return.sqlite","CREATE TABLE returns(state TEXT); INSERT INTO returns VALUES ('unknown')")):
            p=self.source/name
            with sqlite3.connect(p) as db:db.executescript(sql)
            db.close();p.chmod(0o600)
        db=connect(self.source/"testflight")
        request={"invite":"syntheticInvite","request_id":"tf_"+"a"*32,
                 "run_id":"123","source_commit":"b"*40}
        permit=claim(db,request,now=100)
        finish(db,dict(request,nonce=permit["nonce"],outcome="outcome_unknown"))
        db.close()
        for name,data in (("testflight/session.age",b"age-encryption.org/v1\nsynthetic"),("telegram/state.bin",b"synthetic")):
            p=self.source/name;p.write_bytes(data);p.chmod(0o600)
        for name in ("state.sqlite3","tf-private-return.sqlite"):shutil.copy2(self.source/name,self.controller/name)
        shutil.copytree(self.source/"telegram",self.controller/"telegram")
        shutil.copytree(self.source/"testflight",self.state/"testflight")

    def tearDown(self):self.temp.cleanup()
    def test_exact_frozen_copies(self):
        compare(self.source,self.controller,self.state)
        (self.state/"testflight/session.age").write_bytes(b"age-encryption.org/v1\nchanged")
        with self.assertRaises(ValueError):compare(self.source,self.controller,self.state)

    def test_inflight_rejected(self):
        with sqlite3.connect(self.source/"state.sqlite3") as db:db.execute("INSERT INTO tasks VALUES ('sending')")
        db.close()
        shutil.copy2(self.source/"state.sqlite3",self.controller/"state.sqlite3")
        with self.assertRaises(ValueError):compare(self.source,self.controller,self.state)

    def test_catalog_state_requires_all_scopes_idle(self):
        path = self.source / "state.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE metadata(scope TEXT, name TEXT, value TEXT)")
            db.executemany("INSERT INTO metadata VALUES (?, ?, ?)", [
                ("owner", "version_browser", '{"pending":null}'),
                ("other", "version_browser", '{"pending":null}'),
            ])
        db.close()
        shutil.copy2(path, self.controller / path.name)
        compare(self.source, self.controller, self.state)

        for value in ('{"pending":{"rid":"synthetic"}}', 'null', '{invalid'):
            with self.subTest(value=value):
                with sqlite3.connect(path) as db:
                    db.execute("UPDATE metadata SET value=? WHERE scope='other'", (value,))
                db.close()
                shutil.copy2(path, self.controller / path.name)
                with self.assertRaises(ValueError):
                    compare(self.source, self.controller, self.state)

    def test_wal_and_symlink_rejected(self):
        wal=self.source/"state.sqlite3-wal";wal.touch()
        with self.assertRaises(ValueError):compare(self.source,self.controller,self.state)
        wal.unlink()
        path=self.controller/"telegram/state.bin";path.unlink();path.symlink_to(self.source/"telegram/state.bin")
        with self.assertRaises(ValueError):compare(self.source,self.controller,self.state)


    def test_source_report_is_read_only_and_closed(self):
        before={p.relative_to(self.source):p.read_bytes()
                for p in self.source.rglob("*") if p.is_file()}
        report=inspect_source(self.source)
        self.assertEqual(report,{"schema":"ipa-migration-source-v1",
            "controller_snapshot_valid":True,"state_snapshot_valid":True,"snapshot_valid":True})
        self.assertEqual(before,{p.relative_to(self.source):p.read_bytes()
                                for p in self.source.rglob("*") if p.is_file()})
        ledger=self.source/"testflight/acceptance.sqlite"
        ledger.unlink()
        self.assertEqual(inspect_source(self.source),dict(report,state_snapshot_valid=False,snapshot_valid=False))
        self.assertFalse(ledger.exists())
        self.assertNotIn(str(self.source),json.dumps(inspect_source(self.source)))

    def test_unknown_acceptance_is_preserved_and_cannot_rearm(self):
        compare(self.source,self.controller,self.state)
        db=connect(self.state/"testflight")
        try:
            result=claim(db,{"invite":"syntheticInvite","request_id":"tf_"+"c"*32,
                            "run_id":"456","source_commit":"d"*40},now=999999)
            self.assertFalse(result["permitted"])
            self.assertEqual(result["previous_state"],"outcome_unknown")
        finally:
            db.close()
        compare(self.source,self.controller,self.state)

    def test_malformed_identical_acceptance_databases_rejected(self):
        path=self.source/"testflight/acceptance.sqlite"
        for sql in (
            "CREATE TABLE invitations(state TEXT)",
            """CREATE TABLE invitations(invite TEXT,request_id TEXT,run_id TEXT,
                source_commit TEXT,nonce TEXT,expires INTEGER,state TEXT)""",
            """CREATE TABLE invitations(invite TEXT PRIMARY KEY,request_id TEXT,run_id TEXT,
                source_commit TEXT,nonce TEXT,expires INTEGER,state TEXT);
                INSERT INTO invitations(invite,state) VALUES ('synthetic','retryable')""",
            """CREATE TABLE invitations(invite TEXT PRIMARY KEY,request_id TEXT,run_id TEXT,
                source_commit TEXT,nonce TEXT,expires INTEGER,state TEXT);
                INSERT INTO invitations(invite,state) VALUES ('synthetic',NULL)""",
        ):
            with self.subTest(sql=sql):
                path.unlink()
                db=sqlite3.connect(path)
                db.executescript(sql)
                db.close()
                path.chmod(0o600)
                shutil.copy2(path,self.state/"testflight/acceptance.sqlite")
                with self.assertRaises(ValueError):
                    compare(self.source,self.controller,self.state)
                self.assertFalse(inspect_source(self.source)["state_snapshot_valid"])

    def test_unresolved_update_and_unknown_task_state_block_source(self):
        path=self.source/"state.sqlite3"
        db=sqlite3.connect(path)
        db.execute("CREATE TABLE updates(done INTEGER)")
        db.execute("INSERT INTO updates VALUES (0)")
        db.commit()
        db.close()
        self.assertFalse(inspect_source(self.source)["controller_snapshot_valid"])
        db=sqlite3.connect(path)
        db.execute("UPDATE updates SET done=1")
        db.commit()
        db.close()
        self.assertTrue(inspect_source(self.source)["controller_snapshot_valid"])
        for state in ("pending","sending","future_state",None):
            with self.subTest(state=state):
                db=sqlite3.connect(path)
                db.execute("DELETE FROM tasks")
                db.execute("INSERT INTO tasks VALUES (?)",(state,))
                db.commit()
                db.close()
                self.assertFalse(inspect_source(self.source)["controller_snapshot_valid"])

    def test_source_cli_exit_status_and_redaction(self):
        tool=Path(__file__).resolve().parents[1]/"tools/managed_migration.py"
        args=[sys.executable,str(tool),"--source",str(self.source),"--inspect-source"]
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(json.loads(result.stdout)["snapshot_valid"])
        self.assertEqual(result.stderr,"")
        (self.source/"testflight/acceptance.sqlite").unlink()
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertFalse(json.loads(result.stdout)["state_snapshot_valid"])
        self.assertNotIn(str(self.source),result.stdout+result.stderr)
        self.assertFalse((self.source/"testflight/acceptance.sqlite").exists())
        for extra in (["--controller",str(self.controller)],["--state",str(self.state)]):
            self.assertEqual(subprocess.run(args+extra,capture_output=True).returncode,2)

if __name__=="__main__":unittest.main()

