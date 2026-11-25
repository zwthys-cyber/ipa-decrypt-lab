"""Synthetic frozen state comparison; no production state or credentials."""
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from managed_migration import compare

class ManagedMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/"source";self.controller=self.root/"controller";self.state=self.root/"state"
        for p in (self.source,self.controller,self.state,self.source/"testflight",self.source/"telegram"):
            p.mkdir(mode=0o700)
        for name,sql in (
          ("state.sqlite3","CREATE TABLE tasks(state TEXT); INSERT INTO tasks VALUES ('delivered')"),
          ("tf-private-return.sqlite","CREATE TABLE returns(state TEXT); INSERT INTO returns VALUES ('unknown')"),
          ("testflight/acceptance.sqlite","CREATE TABLE invitations(state TEXT); INSERT INTO invitations VALUES ('outcome_unknown')")):
            p=self.source/name
            with sqlite3.connect(p) as db:db.executescript(sql)
            db.close();p.chmod(0o600)
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

if __name__=="__main__":unittest.main()
