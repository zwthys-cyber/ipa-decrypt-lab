"""SQLite contract for isolated link metadata; no storage API or real data."""
import json
from pathlib import Path
import sqlite3
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent
class LinkSQLTests(unittest.TestCase):
    def test_owner_cancel_expiry_and_no_overwrite(self):
        with sqlite3.connect(":memory:") as db:
            for name in ("0001_pilot.sql","0002_links.sql"):
                db.executescript((ROOT/"migrations"/name).read_text())
            sql=json.loads(subprocess.check_output(["node","--input-type=module","-e",
                "import {LINK_SQL} from './private-link.mjs';console.log(JSON.stringify(LINK_SQL))"],cwd=ROOT,text=True))
            job="pilot_"+"a"*32;owner="123";file="syntheticFileID123"
            db.execute("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)",(job,owner,1,"123456","default",1,86400,"waiting_for_runtime"))
            values=(file,"Example.zip",2000000000,"a"*64,100,job,owner)
            self.assertEqual(db.execute(sql["register"],(*values[:-1],"999")).rowcount,0)
            self.assertEqual(db.execute(sql["register"],values).rowcount,1)
            self.assertEqual(db.execute(sql["register"],values).rowcount,0)
            self.assertIsNone(db.execute(sql["lookup"],(job,"999",99)).fetchone())
            self.assertEqual(db.execute(sql["lookup"],(job,owner,99)).fetchone()[0],file)
            self.assertIsNone(db.execute(sql["lookup"],(job,owner,100)).fetchone())
            db.execute("UPDATE pilot_jobs SET state='cancelled' WHERE job_id=?",(job,))
            self.assertIsNone(db.execute(sql["lookup"],(job,owner,99)).fetchone())
if __name__=="__main__":unittest.main()
