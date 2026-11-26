"""Runtime-only online recovery preservation. Never changes source records or stops the service."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import sys
import tarfile
import tempfile
import time

def need(ok):
    if not ok:raise ValueError("source_preservation_failed")
def private(path,directory=False):
    info=path.lstat()
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)) and info.st_mode&0o077==0)
def sha(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def database(source,destination):
    private(source);deadline=time.monotonic()+45
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    def progress(*unused):need(time.monotonic()<deadline)
    with closing(sqlite3.connect(source.resolve().as_uri()+"?mode=ro",uri=True,timeout=3)) as src,          closing(sqlite3.connect(destination)) as dst:
        src.backup(dst,pages=128,progress=progress,sleep=0.05)
        need(dst.execute("PRAGMA quick_check").fetchall()==[("ok",)])
    destination.chmod(0o600)
def copy(source,destination):
    private(source);need(source.stat().st_size<=16*1024*1024)
    destination.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,"rb") as src,os.fdopen(os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"wb") as dst:
        shutil.copyfileobj(src,dst,1024*1024)
def collect(source,config,stage):
    private(source,True);private(config,True);private(stage,True)
    records={};missing=[]
    for name in ("state.sqlite3","tf-private-return.sqlite","testflight/acceptance.sqlite"):
        path=source/name
        if not path.exists():
            need(not path.is_symlink());missing.append(name);continue
        database(path,stage/"state"/name)
    for src,name in ((config/"bot.json","config/bot.json"),(source/"testflight/session.age","state/testflight/session.age")):
        copy(src,stage/name)
    session=stage/"state/testflight/session.age"
    need(22<session.stat().st_size<=256*1024)
    with session.open("rb") as stream:need(stream.read(22)==b"age-encryption.org/v1\n")
    telegram=source/"telegram"
    if telegram.exists():
        private(telegram,True)
        for path in telegram.rglob("*"):
            need(not path.is_symlink())
            if path.is_dir():private(path,True);continue
            private(path)
            if path.name.endswith(("-wal","-shm","-journal")):continue
            relative=path.relative_to(telegram)
            destination=stage/"state/telegram"/relative
            with path.open("rb") as stream:sqlite=stream.read(16)==b"SQLite format 3\x00"
            if sqlite:database(path,destination)
            else:copy(path,destination)
    for required in ("state/state.sqlite3","state/tf-private-return.sqlite","config/bot.json","state/testflight/session.age"):
        need((stage/required).is_file())
    total=0
    for path in sorted(stage.rglob("*")):
        if path.is_file():
            total+=path.stat().st_size
            need(len(records)<500 and total<=100*1024*1024)
            records[path.relative_to(stage).as_posix()]=dict(bytes=path.stat().st_size,sha256=sha(path))
    with closing(sqlite3.connect((stage/"state/state.sqlite3").resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
        counts=dict(db.execute("SELECT state,count(*) FROM tasks GROUP BY state").fetchall())
    need(all(k in ("pending","sending","delivered","cancelled","closed") and type(v) is int and v>=0 for k,v in counts.items()))
    manifest=dict(schema="ipa-online-preservation-v1",frozen=False,cutover_approved=False,
        captured_at=int(time.time()),files=records,missing=missing,task_states=counts,
        session_sha256=sha(session))
    (stage/"manifest.json").write_text(json.dumps(manifest,sort_keys=True)+"\n")
    (stage/"manifest.json").chmod(0o600)
    return manifest
def main():
    os.umask(0o077)
    try:
        need(os.environ.get("LAB_RUNTIME")=="vps" and os.geteuid()==0)
        with tempfile.TemporaryDirectory(prefix=".ipazake-preserve-",dir="/var/tmp") as folder:
            root=Path(folder);collect(Path("/var/lib/ipazake"),Path("/etc/ipazake"),root)
            with tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz") as archive:
                for path in sorted(root.rglob("*")):
                    if path.is_file():archive.add(path,arcname=path.relative_to(root).as_posix(),recursive=False)
        return 0
    except Exception:
        print("source_preservation_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
