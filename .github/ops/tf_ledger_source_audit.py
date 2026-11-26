"""Read-only source inventory for TF migration; no Apple, Telegram or helper execution."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

MAX_DB_BYTES=128*1024*1024
MAX_SCAN_ENTRIES=4096
KNOWN_INVITE="yoNuHexZ"

def need(value):
    if not value:
        raise ValueError("source_audit_failed")

def private(path,directory=False):
    info=path.lstat()
    need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
    need(info.st_mode&0o077==0)
    return info

def database(path):
    """Use SQLite's read-only transaction so live WAL records are included."""
    private(path.parent,True)
    info=private(path)
    need(info.st_size<=MAX_DB_BYTES)
    db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True,timeout=3)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        need(db.execute("PRAGMA quick_check").fetchall()==[("ok",)])
        return db
    except Exception:
        db.close()
        raise

def candidates(root):
    # Inspect names only, never follow links or enter Telegram/application data.
    found=0
    scanned=0
    pending=[(root,0)]
    while pending:
        directory,depth=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                scanned+=1
                need(scanned<=MAX_SCAN_ENTRIES)
                if entry.name in {"acceptance.sqlite","invitation-intents.sqlite"}:
                    need(not entry.is_symlink())
                    need(entry.is_file(follow_symlinks=False))
                    found+=1
                if (depth<3 and entry.is_dir(follow_symlinks=False)
                        and entry.name not in {"telegram","tmp","delivery","downloads"}):
                    pending.append((Path(entry.path),depth+1))
    return found

def inspect(root,now=None,report=None):
    if report is None:
        report={}
    report.update(schema="ipa-tf-source-audit-v1",status="source_audit_failed")
    report["stage"]="root"
    private(root,True)
    report["stage"]="health"
    health_path=root/"health.json"
    need(private(health_path).st_size<=16384)
    health=json.loads(health_path.read_bytes())
    now=int(time.time() if now is None else now)
    need(health.get("state")=="ready" and health.get("task_active") is False)
    need(type(health.get("at")) is int and 0<=now-health["at"]<120)
    report["service_idle_observed"]=True
    report["stage"]="controller"
    with closing(database(root/"state.sqlite3")) as db:
        states=db.execute("""SELECT state,count(*) FROM tasks
            WHERE substr(rid,1,3)='tf_' GROUP BY state""").fetchall()
        need(all(state in {"pending","sending","delivered","cancelled","closed"}
                 and type(count) is int and 0<count<=100000 for state,count in states))
        report["tf_tasks_total"]=sum(count for _,count in states)
        report["tf_tasks_unfinished"]=sum(count for state,count in states if state in {"pending","sending"})
        # Do not expose private request IDs, scopes, invites, users or offsets.
    report["stage"]="session"
    state=root/"testflight"
    private(state,True)
    cipher=state/"session.age"
    info=private(cipher)
    need(22<info.st_size<=256*1024)
    with cipher.open("rb") as stream:
        need(stream.read(22)==b"age-encryption.org/v1\n")
    report["session_ciphertext_present"]=True
    report["stage"]="acceptance"
    acceptance=state/"acceptance.sqlite"
    report["acceptance_ledger_present"]=acceptance.exists() or acceptance.is_symlink()
    report["acceptance_ledger_valid"]=False
    report["known_acceptance_confirmed"]=False
    report["acceptance_rows"]=0
    report["unresolved_acceptance_rows"]=0
    if report["acceptance_ledger_present"]:
        with closing(database(acceptance)) as db:
            columns=db.execute("PRAGMA table_info(invitations)").fetchall()
            need({row[1] for row in columns}==
                 {"invite","request_id","run_id","source_commit","nonce","expires","state"})
            need([row[1] for row in columns if row[5]]==["invite"])
            states=db.execute("SELECT state,count(*) FROM invitations GROUP BY state").fetchall()
            need(all(state in {"intent","membership_verified","outcome_unknown"}
                     and type(count) is int and 0<count<=100000 for state,count in states))
            report["acceptance_rows"]=sum(count for _,count in states)
            report["unresolved_acceptance_rows"]=sum(count for state,count in states if state!="membership_verified")
            report["known_acceptance_confirmed"]=db.execute(
                "SELECT state FROM invitations WHERE invite=?",(KNOWN_INVITE,)).fetchone()==("membership_verified",)
            report["acceptance_ledger_valid"]=True
    report["stage"]="candidates"
    report["acceptance_candidates"]=candidates(root)
    report["stage"]="returns"
    with closing(database(root/"tf-private-return.sqlite")) as db:
        rows=db.execute("SELECT state,count(*) FROM deliveries GROUP BY state").fetchall()
        need(all(state in {"intent","confirmed"} and type(count) is int and 0<count<=100000
                 for state,count in rows))
        report["private_return_rows"]=sum(count for _,count in rows)
        report["private_return_unknown"]=sum(count for state,count in rows if state=="intent")
    report["status"]="source_inventory_observed"
    report["stage"]="complete"
    # This report never approves reconstruction, cutover or new invitation acceptance.
    return report

def main():
    report={"stage":"runtime"}
    try:
        need(os.environ.get("LAB_RUNTIME")=="vps" and os.geteuid()==0)
        result=inspect(Path("/var/lib/ipazake"),report=report)
    except Exception:
        result={"schema":"ipa-tf-source-audit-v1","status":"source_audit_failed","stage":report["stage"]}
    print(json.dumps(result,sort_keys=True))
    return 0 if result["status"]=="source_inventory_observed" else 2

if __name__=="__main__":
    raise SystemExit(main())
