import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from preserve_source import collect, database

class PreserveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/"source";self.config=self.root/"config";self.stage=self.root/"stage"
        for path in (self.source,self.config,self.stage):path.mkdir(mode=0o700)
        (self.source/"testflight").mkdir(mode=0o700)
        (self.config/"bot.json").write_text('{"fixture":"private"}');(self.config/"bot.json").chmod(0o600)
        (self.source/"testflight/session.age").write_bytes(b"age-encryption.org/v1\nsynthetic-envelope")
        (self.source/"testflight/session.age").chmod(0o600)
        for name in ("state.sqlite3","tf-private-return.sqlite"):
            path=self.source/name
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE tasks(state TEXT)");db.execute("INSERT INTO tasks VALUES('pending')")
            path.chmod(0o600)

    def test_online_snapshot_preserves_busy_source_without_claiming_cutover(self):
        result=collect(self.source,self.config,self.stage)
        self.assertFalse(result["frozen"]);self.assertFalse(result["cutover_approved"])
        self.assertEqual(result["task_states"],{"pending":1})
        self.assertIn("testflight/acceptance.sqlite",result["missing"])
        self.assertFalse((self.source/"testflight/acceptance.sqlite").exists())
        with sqlite3.connect(self.source/"state.sqlite3") as db:
            self.assertEqual(db.execute("SELECT * FROM tasks").fetchall(),[("pending",)])
        self.assertEqual((self.stage/"state/state.sqlite3").stat().st_mode&0o777,0o600)

    def test_wal_snapshot_includes_committed_rows(self):
        path=self.source/"state.sqlite3"
        with sqlite3.connect(path) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute("INSERT INTO tasks VALUES('sending')");writer.commit()
            database(path,self.stage/"wal.sqlite")
            with sqlite3.connect(self.stage/"wal.sqlite") as snapshot:
                self.assertEqual(snapshot.execute("SELECT count(*) FROM tasks").fetchone(),(2,))

    def test_symlink_source_is_refused(self):
        path=self.source/"testflight/session.age";path.unlink();path.symlink_to(self.config/"bot.json")
        with self.assertRaises(ValueError):collect(self.source,self.config,self.stage)

if __name__=="__main__":unittest.main()
