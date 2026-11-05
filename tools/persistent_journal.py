"""Private SQLite recovery ledger for a single persistent Telegram controller."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from telegram_queue import QueueError, request_id, require

STATES={"pending","sending","delivered","cancelled","closed"}

class PersistentJournal:
    def __init__(self,path,owner):
        require(type(owner) is int and owner>0,"invalid_journal_identity")
        self.scope=hashlib.sha256(("telegram-owner:"+str(owner)).encode()).hexdigest()
        self.path=Path(path)
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd=os.open(self.path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            require(os.fstat(fd).st_mode & 0o077==0,"insecure_journal_permissions")
        finally:
            os.close(fd)
        self.db=sqlite3.connect(self.path,timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks(
              scope TEXT NOT NULL, rid TEXT NOT NULL, app TEXT NOT NULL,
              state TEXT NOT NULL, at INTEGER NOT NULL, created INTEGER NOT NULL,
              PRIMARY KEY(scope,rid));
            CREATE TABLE IF NOT EXISTS updates(
              scope TEXT NOT NULL, uid INTEGER NOT NULL, at INTEGER NOT NULL,
              done INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scope,uid));
            CREATE TABLE IF NOT EXISTS metadata(
              scope TEXT NOT NULL, name TEXT NOT NULL, value TEXT NOT NULL,
              PRIMARY KEY(scope,name));
        """)
        self.records={}
        self.load()

    def load(self):
        self.records={row[0]:dict(rid=row[0],app=row[1],state=row[2],at=row[3],created=row[4])
            for row in self.db.execute("SELECT rid,app,state,at,created FROM tasks WHERE scope=?",(self.scope,))}
        return self.records

    def write(self,rid,state,app=""):
        request_id(rid)
        require(state in STATES and isinstance(app,str) and
                (not app or re.fullmatch(r"[1-9][0-9]{4,19}",app)),"invalid_journal_record")
        now=int(time.time())
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("""
                INSERT INTO tasks(scope,rid,app,state,at,created) VALUES(?,?,?,?,?,?)
                ON CONFLICT(scope,rid) DO UPDATE SET
                  app=CASE WHEN excluded.app='' THEN tasks.app ELSE excluded.app END,
                  state=excluded.state,at=excluded.at
                """,(self.scope,rid,app,state,now,now))
        self.load()

    def pending(self):
        now=int(time.time())
        return [r for r in self.records.values() if r["state"]=="pending" and 0<=now-r["at"]<86400]

    def daily_submissions(self,now=None):
        stamp=int(time.time() if now is None else now)
        start=stamp//86400*86400
        return self.db.execute("SELECT count(*) FROM tasks WHERE scope=? AND created>=? AND created<?",
                               (self.scope,start,start+86400)).fetchone()[0]

    def claim_update(self,uid):
        require(type(uid) is int and uid>=0,"invalid_update_id")
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            cursor=self.db.execute("INSERT OR IGNORE INTO updates(scope,uid,at) VALUES(?,?,?)",
                                   (self.scope,uid,int(time.time())))
        return cursor.rowcount==1

    def finish_update(self,uid):
        with self.db:
            self.db.execute("UPDATE updates SET done=1 WHERE scope=? AND uid=?",(self.scope,uid))
            self.db.execute("""INSERT INTO metadata(scope,name,value) VALUES(?,'offset',?)
               ON CONFLICT(scope,name) DO UPDATE SET value=excluded.value""",(self.scope,str(uid+1)))

    def offset(self):
        row=self.db.execute("SELECT value FROM metadata WHERE scope=? AND name='offset'",(self.scope,)).fetchone()
        return int(row[0]) if row else 0

    def browser_load(self):
        row=self.db.execute("SELECT value FROM metadata WHERE scope=? AND name='version_browser'",(self.scope,)).fetchone()
        return json.loads(row[0]) if row else None

    def browser_save(self,state):
        data=json.dumps(state,separators=(",",":"))
        require(len(data)<=131072,"version_browser_state_too_large")
        with self.db:
            self.db.execute("""INSERT INTO metadata(scope,name,value) VALUES(?,'version_browser',?)
                ON CONFLICT(scope,name) DO UPDATE SET value=excluded.value""",(self.scope,data))

    def close(self):
        self.db.close()
