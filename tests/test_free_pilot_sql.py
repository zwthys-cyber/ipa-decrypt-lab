"""Execute the free pilot's actual SQL against synthetic SQLite only."""
import json
from pathlib import Path
import sqlite3
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
PILOT=ROOT/"deploy/managed/free-pilot"

class FreePilotSQLTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.db.executescript((PILOT/"migrations/0001_pilot.sql").read_text())
        self.sql=json.loads(subprocess.check_output(
            ["node","--input-type=module","-e","import {SQL} from './worker.mjs';console.log(JSON.stringify(SQL))"],cwd=PILOT,text=True))
    def tearDown(self):self.db.close()
    def add(self,num,owner="123",day=100,update=None):
        update=num if update is None else update
        job="pilot_"+format(num,"032x")
        cursor=self.db.execute(self.sql["insert"],(job,owner,update,"123456","cn",day,day*86400,owner,day,owner))
        return cursor.rowcount
    def test_replay_quota_cancel_and_isolation(self):
        self.assertEqual(self.add(1),1)
        self.assertEqual(self.add(2,update=1),0)
        self.assertEqual(self.add(3),1)
        self.assertEqual(self.add(4),1)
        self.assertEqual(self.add(5),0)
        job="pilot_"+format(1,"032x")
        self.assertEqual(self.db.execute(self.sql["cancel"],("456",job)).rowcount,0)
        self.assertEqual(self.db.execute(self.sql["cancel"],("123",job)).rowcount,1)
        self.assertEqual(self.add(5),0) # Cancelling does not refund daily quota.
        self.assertEqual(self.add(5,day=101),1)
        self.assertEqual(self.add(6,owner="456"),1)
        self.assertEqual(len(self.db.execute(self.sql["recent"],("456",)).fetchall()),1)
    def test_active_cap(self):
        for n in range(30):self.assertEqual(self.add(n+1,day=100+n),1)
        self.assertEqual(self.add(31,day=200),0)
        self.db.execute(self.sql["cancel"],("123","pilot_"+format(1,"032x")))
        self.assertEqual(self.add(31,day=200),1)

if __name__=="__main__":unittest.main()
