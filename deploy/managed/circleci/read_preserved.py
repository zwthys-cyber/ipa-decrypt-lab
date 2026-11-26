"""GitHub-only encrypted-state readback. No source mutations, Apple calls or public private material."""
import base64
from contextlib import closing
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from verify_preservation import verify
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/".github/ops"))
from tf_task_session import validated,RECIPIENT

def need(ok):
    if not ok:raise ValueError("preserved_state_invalid")
def reassemble(pins,env):
    need(pins.get("schema")=="circleci-preserved-source-v1" and pins.get("frozen") is False and
        pins.get("cutover_approved") is False and pins.get("recipient")==RECIPIENT and
        type(pins.get("source_run")) is int and type(pins.get("chunks")) is list and
        1<=len(pins["chunks"])<=20 and len(set(pins["chunks"]))==len(pins["chunks"]))
    parts=[]
    for index,name in enumerate(pins["chunks"],1):
        need(name=="CIRCLECI_MIGRATION_"+str(pins["source_run"])+"_"+str(index).zfill(2))
        value=env.get(name,"");need(type(value) is str and 0<len(value)<=40000)
        raw=base64.b64decode(value,validate=True);need(0<len(raw)<=30000);parts.append(raw)
    raw=b"".join(parts)
    need(raw.startswith(b"age-encryption.org/v1\n") and len(raw)==pins["archive_bytes"] and
        len(raw)<=1024*1024 and hashlib.sha256(raw).hexdigest()==pins["archive_sha256"])
    return raw
def decrypt(cipher,identity,env):
    with tempfile.TemporaryDirectory(prefix="circle-state-key-") as directory:
        path=Path(directory)/"key.txt"
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"w") as stream:
            stream.write(identity)
        child={k:env[k] for k in ("PATH","HOME","LANG") if k in env}
        result=subprocess.run(["age","--decrypt","--identity",str(path)],input=cipher,
            capture_output=True,timeout=30,env=child)
        need(result.returncode==0 and 0<len(result.stdout)<=1024*1024)
        return result.stdout
def saved_session(pins,env):
    need(pins.get("session_secret")=="TF_SAVED_SESSION_AGE_B64")
    value=env.get("TF_SAVED_SESSION_AGE_B64","");need(0<len(value)<=44000)
    cipher=base64.b64decode(value,validate=True)
    need(hashlib.sha256(cipher).hexdigest()==pins["session_sha256"])
    raw=decrypt(cipher,env["DELIVERY_AGE_IDENTITY"],env)
    need(len(raw)<=256*1024);validated(json.loads(raw))
    return raw

def main():
    try:
        need(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab" and
            os.environ.get("GITHUB_REF")=="refs/heads/upgrade/managed-runtime-v0.2")
        pins=json.loads(Path(__file__).with_name("source-state-pins.json").read_text())
        cipher=reassemble(pins,os.environ);session=saved_session(pins,os.environ)
        compressed=decrypt(cipher,os.environ["DELIVERY_AGE_IDENTITY"],os.environ)
        with tempfile.TemporaryDirectory(prefix="circle-preserved-read-") as directory:
            folder=Path(directory)
            receipt=verify(io.BytesIO(compressed),folder/"verified")
            # Materialize only the private controller snapshot needed for bounded state counts.
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(compressed),mode="r:gz") as archive:
                member=archive.getmember("state/state.sqlite3")
                need(member.isfile() and member.size<=16*1024*1024)
                raw=archive.extractfile(member).read(16*1024*1024+1);need(len(raw)==member.size)
            dbpath=folder/"controller.sqlite"
            with os.fdopen(os.open(dbpath,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"wb") as stream:stream.write(raw)
            with closing(sqlite3.connect(dbpath.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)) as db:
                cutoff=int(time.time())-86400
                pending_old=db.execute("SELECT count(*) FROM tasks WHERE state='pending' AND at<?",(cutoff,)).fetchone()[0]
                pending_recent=db.execute("SELECT count(*) FROM tasks WHERE state='pending' AND at>=?",(cutoff,)).fetchone()[0]
                unfinished=db.execute("SELECT count(*) FROM updates WHERE done!=1 OR done IS NULL").fetchone()[0]
        output=dict(schema="circleci-preserved-state-readback-v1",archive_from_secrets_verified=True,
            tf_session_from_secret_validated=True,source_run=pins["source_run"],frozen=False,cutover_approved=False,
            files=receipt["files"],task_states=receipt["task_states"],pending_older_than_day=pending_old,
            pending_recent=pending_recent,unfinished_updates=unfinished,
            acceptance_ledger_present=receipt["acceptance_ledger_present"],apple_operation=False)
        print(json.dumps(output,sort_keys=True))
        Path("preserved-state-readback.json").write_text(json.dumps(output,sort_keys=True)+"\n")
        return 0
    except Exception:
        print("preserved_state_readback_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
