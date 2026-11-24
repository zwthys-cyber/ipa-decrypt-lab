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
            db.execute("PRAGMA foreign_keys=ON")
            for name in ("0001_pilot.sql","0002_links.sql","0003_links_10gb.sql","0004_retired_links.sql"):
                db.executescript((ROOT/"migrations"/name).read_text())
            sql=json.loads(subprocess.check_output(["node","--input-type=module","-e",
                "import {LINK_SQL} from './private-link.mjs';console.log(JSON.stringify(LINK_SQL))"],cwd=ROOT,text=True))
            job="pilot_"+"a"*32;owner="123";file="syntheticFileID123"
            db.execute("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)",(job,owner,1,"123456","default",1,86400,"waiting_for_runtime"))
            values=(file,"Example.zip",10000000000,"a"*64,100,job,owner)
            self.assertEqual(db.execute(sql["register"],(*values[:-1],"999")).rowcount,0)
            self.assertEqual(db.execute(sql["register"],values).rowcount,1)
            self.assertEqual(db.execute(sql["register"],values).rowcount,0)
            self.assertIsNone(db.execute(sql["lookup"],(job,"999",99)).fetchone())
            self.assertEqual(db.execute(sql["lookup"],(job,owner,99)).fetchone()[0],file)
            self.assertIsNone(db.execute(sql["lookup"],(job,owner,100)).fetchone())
            db.execute("UPDATE pilot_jobs SET state='cancelled' WHERE job_id=?",(job,))
            self.assertIsNone(db.execute(sql["lookup"],(job,owner,99)).fetchone())
            receipt=(job,owner,file,"Example.zip",10000000000,"a"*64)
            self.assertEqual(db.execute(sql["retire"],(200,*receipt,99)).rowcount,0)
            self.assertEqual(db.execute(sql["retire"],(200,*receipt,100)).rowcount,1)
            self.assertEqual(db.execute(sql["retire"],(300,*receipt,100)).rowcount,1)
            self.assertEqual(db.execute("SELECT retired_at FROM pilot_links").fetchone(),(200,))
    def test_migration_preserves_metadata_and_enforces_64bit_cap(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("PRAGMA foreign_keys=ON")
            for name in ("0001_pilot.sql","0002_links.sql"):
                db.executescript((ROOT/"migrations"/name).read_text())
            jobs=["pilot_"+format(n,"032x") for n in range(1,5)]
            for n,job in enumerate(jobs,1):
                db.execute("INSERT INTO pilot_jobs VALUES(?,?,?,?,?,?,?,?)",(job,"123",n,"123456","default",1,86400,"waiting_for_runtime"))
            original=(jobs[0],"123","syntheticOriginal123","Original.zip",2000000000,"a"*64,100)
            db.execute("INSERT INTO pilot_links VALUES(?,?,?,?,?,?,?)",original)
            db.commit()
            db.executescript((ROOT/"migrations"/"0003_links_10gb.sql").read_text())
            self.assertEqual(db.execute("SELECT * FROM pilot_links WHERE job_id=?",(jobs[0],)).fetchone(),original)
            for job,size in ((jobs[1],4294967297),(jobs[2],10000000000)):
                db.execute("INSERT INTO pilot_links VALUES(?,?,?,?,?,?,?)",(job,"123","syntheticFile"+job[-12:],"Large.zip",size,"b"*64,100))
                self.assertEqual(db.execute("SELECT bytes FROM pilot_links WHERE job_id=?",(job,)).fetchone()[0],size)
            for size in (10000000001,1.5,0,-1):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("INSERT INTO pilot_links VALUES(?,?,?,?,?,?,?)",(jobs[3],"123","syntheticRejected123","Large.zip",size,"c"*64,100))
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
if __name__=="__main__":unittest.main()
