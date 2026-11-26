"""Build an encrypted historical TF ledger candidate from pinned, read-only evidence.

Never installs source state, calls Apple, accepts an invite or sends a message.
"""
from contextlib import closing
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from testflight_state import connect

REPO="zwthys-cyber/ipa-decrypt-lab"
AUDIT_RUN=45811165425
AUDIT_SOURCE="6d9e4c950ec583ef0d863dd7ef39355df3a5ba39"
AUDIT_JOB=139879207590
EXPECTED_RESEARCH_RUNS=[42650011477,42650873653,42652233101,42654419361,42655279948,42656943897,42657854276,42660282023,42662277216,42665103395,42667404119,42669754544,42669967018,42670588627,42670772636,42670934355,42672190788,42672595272,42675996429,42676403958,42677280328,42677692634,42677924391,42678311930,42678760191,42680721956,42681544982,42681917359,42682410339,42682894405,42683673733,42684108574,42684530592,42685200221,42685984682,42686348741,42686722193,42687012113,42687594002,42688443638,42688988859,42689737849,42690498519,42692803345,42693913451,42694342484,42694923538,42696261040,42697014857,42697436346,42698306052,42699070274,42699396608,42699765568,42700045757,42700371218,42700737247,42701117321,42704626300]
INTENT_PATH=".github/ops/tf_invite_intents/298ad9a0bb3e8e78ebccad99f91c2f7273608575e54f35191206fc2a3fde9019.json"
INTENT_BLOB="7e233cd2eab2009b961bf8718ebf822fe6a6dc7f"
RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"
HISTORY=(
    (42692803345,"688b5356aa33a9653517f62445856a08c72819c4",129416695490,"failure","tf-accept-control-v1","acceptance_outcome_unverified"),
    (42694923538,"e86e8c8773955951492dcd1b31b1c5c75babbd34",129424099888,"success","tf-invite-resolution-v1","membership_verified"),
    (42714371079,"3620bca910a69c419cfb63d8d4623ceb5d5cc2d9",129491957022,"success","tf-worker-result-v1","encrypted_artifact_ready"),
)

def need(value):
    if not value:
        raise ValueError("history_recovery_failed")

def receipts(log,schema):
    need(type(log) is str and len(log)<=32*1024*1024)
    result=[]
    for line in log.splitlines():
        pos=line.find("{")
        if pos<0:
            continue
        try:
            value=json.loads(line[pos:])
        except ValueError:
            continue
        if type(value) is dict and value.get("schema")==schema:
            result.append(value)
    return result

def run_valid(value,identifier,source,conclusion,path,branch="main"):
    need(type(value) is dict and value.get("id")==identifier and value.get("head_sha")==source
         and value.get("run_attempt")==1 and value.get("head_branch")==branch
         and value.get("status")=="completed" and value.get("conclusion")==conclusion
         and value.get("path")==path)

def audit_valid(value):
    expected={"acceptance_candidates":0,"acceptance_ledger_present":False,
              "acceptance_ledger_valid":False,"acceptance_rows":0,"health_recent":True,
              "known_acceptance_confirmed":False,"private_return_rows":1,
              "private_return_unknown":0,"schema":"ipa-tf-source-audit-v1",
              "service_idle_observed":True,"session_ciphertext_present":True,
              "session_matches_promoted_ciphertext":True,"stage":"complete",
              "status":"source_inventory_observed","tf_tasks_total":1,
              "tf_tasks_unfinished":0,"unresolved_acceptance_rows":0}
    need(type(value) is dict and set(value)==set(expected))
    need(all(type(value[k]) is type(v) and value[k]==v for k,v in expected.items()))

def packet_valid(packet,payload):
    keys={"schema","worker_run","source_commit","nonce","expires","account_binding",
          "record_path","ciphertext_b64","cipher_sha256"}
    need(type(packet) is dict and set(packet)==keys)
    need(packet["schema"]=="tf-invite-intent-packet-v1"
         and packet["record_path"]==INTENT_PATH and packet["worker_run"]=="42692803345"
         and packet["source_commit"]==HISTORY[0][1])
    need(re.fullmatch(r"[a-f0-9]{32}",packet["nonce"]) is not None
         and re.fullmatch(r"[a-f0-9]{64}",packet["account_binding"]) is not None)
    cipher=base64.b64decode(packet["ciphertext_b64"],validate=True)
    need(0<len(cipher)<=8192 and cipher.startswith(b"age-encryption.org/v1\n")
         and hashlib.sha256(cipher).hexdigest()==packet["cipher_sha256"])
    need(type(payload) is dict and set(payload)=={"schema","worker_run","source_commit","nonce",
        "issued_at","expires","account_binding","app_binding","invite","origin_run","origin_source"})
    need(payload["schema"]=="tf-invite-intent-v1" and payload["invite"]=="yoNuHexZ"
         and type(payload["app_binding"]) is str
         and re.fullmatch(r"[a-f0-9]{64}",payload["app_binding"]) is not None)
    need(all(payload[k]==packet[k] for k in ("worker_run","source_commit","nonce","expires","account_binding")))
    need(payload["origin_run"]=="42650873653"
         and payload["origin_source"]=="19244adbe73f71156a91a5c1cb20965925928054")
    # Expired historical intent is evidence only. It never becomes a live permit.
    need(type(payload["issued_at"]) is int and type(payload["expires"]) is int
         and 0<payload["expires"]-payload["issued_at"]<=600)

def history_valid(index,values):
    expected=HISTORY[index]
    final=[value for value in values if value.get("status")==expected[5]]
    need(len(final)==1)
    value=final[0]
    need(value.get("run_id")==str(expected[0]) and value.get("source_commit")==expected[1])
    if index==0:
        need(value.get("acceptance_attempted") is True and value.get("post_response_confirmed") is True
             and value.get("invitation_accepted") is False)
    else:
        need(value.get("acceptance_attempted") is False and value.get("invitation_accepted") is True)
    need(not any(v.get("acceptance_attempted") is True for v in values) if index else
         not any(v.get("invitation_accepted") is True for v in values))

def gh(path,text=False):
    env={k:os.environ[k] for k in ("PATH","HOME","LANG","GH_TOKEN") if k in os.environ}
    result=subprocess.run(["gh","api","repos/"+REPO+path],capture_output=True,timeout=60,env=env)
    need(result.returncode==0 and len(result.stdout)<=32*1024*1024)
    return result.stdout.decode() if text else json.loads(result.stdout)

def collect():
    run_valid(gh("/actions/runs/"+str(AUDIT_RUN)),AUDIT_RUN,AUDIT_SOURCE,"success",
              ".github/workflows/tf-ledger-source-audit.yml","upgrade/managed-runtime-v0.2")
    jobs=gh("/actions/runs/"+str(AUDIT_RUN)+"/jobs?per_page=100")
    need(any(j.get("id")==AUDIT_JOB and j.get("name")=="source" and j.get("conclusion")=="success"
             for j in jobs["jobs"]))
    audit=receipts(gh("/actions/jobs/"+str(AUDIT_JOB)+"/logs",True),"ipa-tf-source-audit-v1")
    need(len(audit)==1)
    audit_valid(audit[0])
    for index,(identifier,source,job,conclusion,schema,status) in enumerate(HISTORY):
        path=".github/workflows/"+("testflight-private-delivery.yml" if index==2 else "testflight-virtual.yml")
        run_valid(gh("/actions/runs/"+str(identifier)),identifier,source,conclusion,path)
        jobs=gh("/actions/runs/"+str(identifier)+"/jobs?per_page=100")["jobs"]
        need(any(j.get("id")==job and j.get("conclusion")==conclusion for j in jobs))
        history_valid(index,receipts(gh("/actions/jobs/"+str(job)+"/logs",True),schema))
    # Fail on newer production or research history rather than assuming no new accepts.
    for workflow,count in (("testflight-private-delivery.yml",1),("testflight-virtual.yml",59)):
        runs=gh("/actions/workflows/"+workflow+"/runs?per_page=100")
        need(runs["total_count"]==count and len(runs["workflow_runs"])==count)
        expected=EXPECTED_RESEARCH_RUNS if count==59 else [42714371079]
        need(sorted(r["id"] for r in runs["workflow_runs"])==expected)
    info=gh("/contents/"+INTENT_PATH+"?ref="+AUDIT_SOURCE)
    need(info.get("sha")==INTENT_BLOB and info.get("encoding")=="base64")
    packet=json.loads(base64.b64decode(info["content"]))
    return packet

def candidate(root):
    state=root/"testflight"
    state.mkdir(mode=0o700)
    with closing(connect(state)) as db:
        row=db.execute("SELECT * FROM invitations").fetchall()
        need(row==[("yoNuHexZ","historical","42692803345",HISTORY[0][1],"",0,"membership_verified")])
        db.execute("CREATE TABLE recovery_provenance(name TEXT PRIMARY KEY,value TEXT NOT NULL)")
        with db:
            db.executemany("INSERT INTO recovery_provenance VALUES (?,?)",[
                ("schema","ipa-tf-history-recovery-v1"),("source_audit_run",str(AUDIT_RUN)),
                ("source_audit_commit",AUDIT_SOURCE),("intent_blob",INTENT_BLOB),
                ("acceptance_run","42692803345"),("membership_run","42694923538"),
                ("fresh_source_recheck_required","true"),("production_installed","false")])
    path=state/"acceptance.sqlite"
    need(path.stat().st_mode&0o077==0)
    return path

def main():
    os.umask(0o077)
    try:
        need(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("GITHUB_RUN_ATTEMPT")=="1"
             and os.environ.get("GITHUB_REPOSITORY")==REPO
             and os.environ.get("GITHUB_REF") in {"refs/heads/main","refs/heads/upgrade/managed-runtime-v0.2"})
        packet=collect()
        with tempfile.TemporaryDirectory(prefix="tf-history-recovery-",dir=os.environ["RUNNER_TEMP"]) as folder:
            root=Path(folder)
            key=root/"identity"
            key.write_text(os.environ["DELIVERY_AGE_IDENTITY"])
            key.chmod(0o600)
            public={k:os.environ[k] for k in ("PATH","HOME","LANG") if k in os.environ}
            actual=subprocess.run(["age-keygen","-y",str(key)],capture_output=True,timeout=20,env=public)
            need(actual.returncode==0 and actual.stdout.decode().strip()==RECIPIENT)
            decrypted=subprocess.run(["age","-d","-i",str(key)],
                input=base64.b64decode(packet["ciphertext_b64"]),capture_output=True,timeout=20,env=public)
            need(decrypted.returncode==0 and 0<len(decrypted.stdout)<=4096)
            packet_valid(packet,json.loads(decrypted.stdout))
            ledger=candidate(root)
            encrypted=root/"acceptance.sqlite.age"
            result=subprocess.run(["age","-r",RECIPIENT,"-o",str(encrypted),str(ledger)],
                                  capture_output=True,timeout=20,env=public)
            need(result.returncode==0 and encrypted.is_file())
            restored=root/"restored.sqlite"
            result=subprocess.run(["age","-d","-i",str(key),"-o",str(restored),str(encrypted)],
                                  capture_output=True,timeout=20,env=public)
            need(result.returncode==0 and restored.read_bytes()==ledger.read_bytes())
            output=Path("tf-history-recovery-out")
            output.mkdir(mode=0o700)
            cipher=encrypted.read_bytes()
            (output/"acceptance.sqlite.age").write_bytes(cipher)
            receipt={"schema":"ipa-tf-history-recovery-v1","status":"encrypted_candidate_ready",
                     "source_audit_run":str(AUDIT_RUN),"source_audit_commit":AUDIT_SOURCE,
                     "record_count":1,"historical_membership_verified":True,
                     "requires_fresh_source_audit":True,"production_installed":False,
                     "source_modified":False,"apple_requests":False,"plaintext_published":False,
                     "ciphertext_sha256":hashlib.sha256(cipher).hexdigest()}
            data=json.dumps(receipt,sort_keys=True)+"\n"
            (output/"receipt.json").write_text(data)
            (output/"SHA256SUMS").write_text("".join(
                hashlib.sha256((output/name).read_bytes()).hexdigest()+"  "+name+"\n"
                for name in ("acceptance.sqlite.age","receipt.json")))
            print(data,end="")
        return 0
    except Exception:
        print("history_recovery_failed",file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
