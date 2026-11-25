"""Offline frozen-snapshot comparison; never copies, edits or prints private state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys

CONTROLLER_DBS=("state.sqlite3","tf-private-return.sqlite")
STATE_DBS=("testflight/acceptance.sqlite",)
STATE_FILES=("testflight/session.age",)

def need(condition):
    if not condition:raise ValueError("migration_check_failed")

def private(path, directory=False):
    info=path.lstat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    need(info.st_mode&0o077==0)

def digest(path):
    private(path)
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda:stream.read(1024*1024),b""):h.update(data)
    return h.hexdigest()

def check_db(root,name,controller=False):
    path=root/name
    private(path)
    # A frozen, checkpointed database must not depend on WAL/SHM/journal sidecars.
    for suffix in ("-wal","-shm","-journal"):
        side=Path(str(path)+suffix)
        need(not side.exists() and not side.is_symlink())
    with sqlite3.connect(path.resolve().as_uri()+"?mode=ro&immutable=1",uri=True) as db:
        need(db.execute("PRAGMA quick_check").fetchall()==[("ok",)])
        if controller:
            need(db.execute("SELECT count(*) FROM tasks WHERE state IN ('pending','sending')").fetchone()==(0,))
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone():
                for (value,) in db.execute("SELECT value FROM metadata WHERE name='version_browser'"):
                    need(isinstance(value, str) and len(value) <= 2 * 1024 * 1024)
                    browser = json.loads(value)
                    need(isinstance(browser, dict) and browser.get("pending") is None)
    return digest(path)

def tree(root):
    private(root,True)
    values={}
    for directory,dirs,files in os.walk(root,followlinks=False):
        current=Path(directory)
        for name in dirs:private(current/name,True)
        for name in files:
            path=current/name
            values[path.relative_to(root).as_posix()]=digest(path)
    need(bool(values))
    return values

def inventory(root,kind):
    private(root,True)
    if kind=="controller":
        return {"databases":{name:check_db(root,name,name=="state.sqlite3") for name in CONTROLLER_DBS},
                "telegram":tree(root/"telegram")}
    if kind=="state":
        private(root/"testflight",True)
        cipher=root/STATE_FILES[0]
        private(cipher)
        with cipher.open("rb") as stream:need(stream.read(22)==b"age-encryption.org/v1\n")
        need(0<cipher.stat().st_size<=256*1024)
        return {"databases":{name:check_db(root,name) for name in STATE_DBS},
                "cipher":digest(cipher)}
    raise ValueError("migration_check_failed")

def compare(source,controller,state):
    # These are separate OFFLINE volumes or staging snapshots; no running processes.
    roots=[p.resolve(strict=True) for p in (source,controller,state)]
    need(len(set(roots))==3)
    need(not any(a in b.parents for a in roots for b in roots if a!=b))
    for path in (source,controller,state):private(path,True)
    need(inventory(source,"controller")==inventory(controller,"controller"))
    need(inventory(source,"state")==inventory(state,"state"))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("source","controller","state"):parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args()
    try:compare(args.source,args.controller,args.state)
    except Exception:
        print("migration_check_failed",file=sys.stderr);return 2
    print("migration_snapshot_match")
    return 0

if __name__=="__main__":raise SystemExit(main())
