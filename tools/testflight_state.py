"""VPS ciphertext storage and durable, at-most-once TestFlight acceptance permits.

Never decrypts Apple state, logs in, calls Apple or sends Telegram messages.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import tempfile
import time

ROOT=Path("/var/lib/ipazake/testflight")
ORIGIN="42650873653"
def need(value):
    if not value:raise ValueError("testflight_state_invalid")
def validate_request(value,finish=False):
    keys={"invite","request_id","run_id","source_commit"}|({"nonce","outcome"} if finish else set())
    need(type(value) is dict and set(value)==keys)
    need(type(value["invite"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{6,80}",value["invite"]))
    need(type(value["request_id"]) is str and re.fullmatch(r"tf_[a-f0-9]{32}",value["request_id"]))
    need(type(value["run_id"]) is str and re.fullmatch(r"[1-9][0-9]{0,19}",value["run_id"]))
    need(type(value["source_commit"]) is str and re.fullmatch(r"[a-f0-9]{40}",value["source_commit"]))
    if finish:
        need(type(value["nonce"]) is str and re.fullmatch(r"[a-f0-9]{32}",value["nonce"]))
        need(value["outcome"] in {"membership_verified","outcome_unknown"})
    return value
def connect(root):
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    need(not root.is_symlink() and root.stat().st_mode&0o077==0)
    path=root/"acceptance.sqlite"
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:need(os.fstat(fd).st_mode&0o077==0)
    finally:os.close(fd)
    db=sqlite3.connect(path,timeout=20)
    db.execute("PRAGMA synchronous=FULL")
    db.execute("""CREATE TABLE IF NOT EXISTS invitations(
        invite TEXT PRIMARY KEY,request_id TEXT,run_id TEXT,source_commit TEXT,nonce TEXT,
        expires INTEGER,state TEXT NOT NULL)""")
    # Import the already confirmed historical acceptance; never rearm it.
    db.execute("INSERT OR IGNORE INTO invitations VALUES(?,?,?,?,?,?,?)",
        ("yoNuHexZ","historical","42692803345","688b5356aa33a9653517f62445856a08c72819c4","",0,"membership_verified"))
    db.commit();return db
def claim(db,value,now=None):
    value=validate_request(value);now=int(time.time() if now is None else now)
    db.execute("BEGIN IMMEDIATE")
    try:
        previous=db.execute("SELECT state FROM invitations WHERE invite=?",(value["invite"],)).fetchone()
        if previous:db.rollback();return {"schema":"tf-accept-permit-v1","permitted":False,"previous_state":previous[0]}
        nonce=secrets.token_hex(16);expires=now+300
        db.execute("INSERT INTO invitations VALUES(?,?,?,?,?,?,?)",
            (value["invite"],value["request_id"],value["run_id"],value["source_commit"],nonce,expires,"intent"))
        db.commit()
        return dict(value,schema="tf-accept-permit-v1",permitted=True,nonce=nonce,expires=expires)
    except Exception:db.rollback();raise
def finish(db,value):
    value=validate_request(value,True)
    with db:
        row=db.execute("""SELECT state FROM invitations WHERE invite=? AND request_id=? AND run_id=?
            AND source_commit=? AND nonce=?""",tuple(value[k] for k in ("invite","request_id","run_id","source_commit","nonce"))).fetchone()
        need(row is not None and row[0] in {"intent",value["outcome"]})
        db.execute("UPDATE invitations SET state=? WHERE invite=?",(value["outcome"],value["invite"]))
    return {"schema":"tf-accept-finish-v1","recorded":True}
def install_cipher(root,value):
    need(type(value) is dict and set(value)=={"schema","origin_run","ciphertext_b64","sha256"})
    need(value["schema"]=="tf-durable-state-v1" and value["origin_run"]==ORIGIN)
    cipher=base64.b64decode(value["ciphertext_b64"],validate=True)
    need(0<len(cipher)<=256*1024 and cipher.startswith(b"age-encryption.org/v1\n"))
    digest=hashlib.sha256(cipher).hexdigest();need(digest==value["sha256"])
    root.mkdir(mode=0o700,parents=True,exist_ok=True);need(not root.is_symlink() and root.stat().st_mode&0o077==0)
    path=root/"session.age"
    # Immutable first promotion. Any later maintenance needs a separately reviewed replacement.
    fd,temporary=tempfile.mkstemp(prefix=".session-",dir=root)
    try:
        with os.fdopen(fd,"wb") as stream:stream.write(cipher);stream.flush();os.fsync(stream.fileno())
        try:os.link(temporary,path)
        except FileExistsError:
            need(not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest)
    finally:Path(temporary).unlink(missing_ok=True)
    return {"schema":"tf-state-status-v1","ready":True,"origin_run":ORIGIN,"sha256":digest,"bytes":len(cipher)}
def status(root):
    path=root/"session.age"
    if not path.is_file() or path.is_symlink():return {"schema":"tf-state-status-v1","ready":False}
    cipher=path.read_bytes();need(0<len(cipher)<=256*1024 and cipher.startswith(b"age-encryption.org/v1\n"))
    return {"schema":"tf-state-status-v1","ready":True,"origin_run":ORIGIN,"sha256":hashlib.sha256(cipher).hexdigest(),"bytes":len(cipher)}
def main():
    os.umask(0o077)
    result={"schema":"tf-state-operation-v1","status":"failed"}
    try:
        need(os.environ.get("LAB_RUNTIME")=="vps" and os.geteuid()==0)
        operation=sys.argv[1]
        if operation=="status":result=status(ROOT)
        else:
            raw=sys.stdin.buffer.read(400001);need(len(raw)<=400000);value=json.loads(raw)
            if operation=="install":result=install_cipher(ROOT,value)
            else:
                db=connect(ROOT)
                try:
                    if operation=="claim":result=claim(db,value)
                    elif operation=="finish":result=finish(db,value)
                    else:raise ValueError()
                finally:db.close()
    except Exception:pass
    print(json.dumps(result,sort_keys=True),flush=True)
    return 2 if result.get("status")=="failed" else 0
if __name__=="__main__":raise SystemExit(main())
