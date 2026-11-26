"""Synthetic source audit contracts. Never connects to a VPS or network."""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"tools"))
from testflight_state import connect,claim
spec=importlib.util.spec_from_file_location("source_audit",Path(__file__).with_name("tf_ledger_source_audit.py"))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.root.chmod(0o700)
        (self.root/"testflight").mkdir(mode=0o700)
        for name,data in (
            ("health.json",json.dumps({"state":"ready","task_active":False,"at":100}).encode()),
            ("testflight/session.age",b"age-encryption.org/v1\nsynthetic-private-payload"),
        ):
            path=self.root/name
            path.write_bytes(data)
            path.chmod(0o600)
        for name,sql in (
            ("state.sqlite3","CREATE TABLE tasks(rid TEXT,state TEXT); INSERT INTO tasks VALUES ('tf_private_request','delivered')"),
            ("tf-private-return.sqlite","CREATE TABLE deliveries(request TEXT PRIMARY KEY,state TEXT); INSERT INTO deliveries VALUES ('private-return','confirmed')"),
        ):
            path=self.root/name
            with closing(sqlite3.connect(path)) as db:
                db.executescript(sql)
            path.chmod(0o600)

    def tearDown(self):
        self.temp.cleanup()

    def read(self):
        return audit.inspect(self.root,now=100)

    def test_missing_lazy_ledger_is_reported_without_creation(self):
        before={p.relative_to(self.root):p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result=self.read()
        self.assertEqual(result["status"],"source_inventory_observed")
        self.assertFalse(result["acceptance_ledger_present"])
        self.assertEqual(result["acceptance_candidates"],0)
        self.assertEqual(result["tf_tasks_total"],1)
        self.assertEqual(before,{p.relative_to(self.root):p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        public=json.dumps(result)
        for private in (str(self.root),"tf_private_request","private-return","synthetic-private-payload"):
            self.assertNotIn(private,public)

    def test_existing_ledger_counts_without_rearming_unknown_intents(self):
        with closing(connect(self.root/"testflight")) as db:
            claim(db,{"invite":"privateInvite","request_id":"tf_"+"a"*32,
                      "run_id":"123","source_commit":"b"*40},now=1)
        path=self.root/"testflight/acceptance.sqlite"
        before=path.read_bytes()
        report=self.read()
        self.assertTrue(report["acceptance_ledger_valid"])
        self.assertTrue(report["known_acceptance_confirmed"])
        self.assertEqual(report["acceptance_rows"],2)
        self.assertEqual(report["unresolved_acceptance_rows"],1)
        self.assertEqual(report["acceptance_candidates"],1)
        self.assertEqual(path.read_bytes(),before)
        self.assertNotIn("privateInvite",json.dumps(report))

    def test_live_wal_rows_are_observed(self):
        path=self.root/"state.sqlite3"
        with closing(sqlite3.connect(path)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO tasks VALUES ('tf_wal_only','pending')")
            writer.commit()
            self.assertTrue(Path(str(path)+"-wal").exists())
            result=self.read()
            self.assertEqual(result["tf_tasks_total"],2)
            self.assertEqual(result["tf_tasks_unfinished"],1)

    def test_busy_stale_or_malformed_health_is_rejected(self):
        path=self.root/"health.json"
        for data in ({"state":"ready","task_active":True,"at":100},
                     {"state":"ready","task_active":False,"at":-21},
                     {"state":"failed","task_active":False,"at":100},
                     {"state":"ready","task_active":False,"at":True}):
            with self.subTest(data=data):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    self.read()

    def test_links_permissions_and_malformed_ledger_rejected(self):
        path=self.root/"testflight/acceptance.sqlite"
        path.symlink_to(self.root/"state.sqlite3")
        with self.assertRaises(ValueError):
            self.read()
        path.unlink()
        with closing(sqlite3.connect(path)) as db:
            db.execute("CREATE TABLE invitations(state TEXT)")
        path.chmod(0o600)
        with self.assertRaises(ValueError):
            self.read()
        path.unlink()
        (self.root/"testflight").chmod(0o755)
        with self.assertRaises(ValueError):
            self.read()

    def test_scan_finds_old_candidate_without_reading_its_contents(self):
        old=self.root/"backup"
        old.mkdir(mode=0o700)
        path=old/"acceptance.sqlite"
        path.write_bytes(b"not a database; candidate only")
        result=self.read()
        self.assertEqual(result["acceptance_candidates"],1)
        self.assertFalse(result["acceptance_ledger_present"])

if __name__=="__main__":
    unittest.main()
