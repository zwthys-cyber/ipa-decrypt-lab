"""GitHub-only authenticated backup recovery planning. Never activates, polls or dispatches."""
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
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from runtime_cloud import NoRedirect
STAGE="context"
def stage(name):
    global STAGE
    STAGE=name
from retain_canary_archive import PREFIX,assemble,REPO,BRANCH,RUN,SOURCE,DIGEST
from read_preserved import decrypt
from verify_preservation import verify,PROMOTED
RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"

def need(ok):
    if not ok:raise ValueError("offline_recovery_invalid")

def database(root,name,raw):
    need(type(raw) is bytes and 0<len(raw)<=16*1024*1024)
    path=root/name
    with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"wb") as stream:
        stream.write(raw)
    db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        need(db.execute("PRAGMA quick_check").fetchall()==[("ok",)])
        return db
    except Exception:
        db.close();raise

def table(db,name,limit=5000):
    need(name in ("tasks","updates","metadata","deliveries","invitations"))
    cursor=db.execute("SELECT * FROM "+name+" LIMIT "+str(limit+1))
    columns=[field[0] for field in cursor.description]
    values=cursor.fetchall();need(len(values)<=limit)
    rows=[]
    for value in values:
        need(all(item is None or type(item) in (str,int,float) for item in value))
        row=dict(zip(columns,value));need(len(json.dumps(row).encode())<=4*1024*1024)
        rows.append(row)
    return rows

def plan(compressed,root,owner,index,now=None,token_probe=None):
    now=int(time.time()) if now is None else now
    need(type(owner) is str and re.fullmatch(r"[1-9][0-9]{0,15}",owner) and int(owner)<=9007199254740991)
    need(index["source_run"]==RUN and index["source_sha"]==SOURCE and index["archive_sha256"]==DIGEST and index["permanent_handoff"] is False)
    stage("authenticate_archive")
    inventory=verify(io.BytesIO(compressed),root/"verified",expected_frozen=True)
    with tarfile.open(fileobj=io.BytesIO(compressed),mode="r:gz") as archive:
        def read(name,limit):
            member=archive.getmember(name);need(member.isfile() and member.size<=limit)
            raw=archive.extractfile(member).read(limit+1);need(len(raw)==member.size);return raw
        stage("snapshot_binding")
        manifest=json.loads(read("manifest.json",65536))
        pause=manifest.get("bounded_pause",{})
        need(type(manifest.get("captured_at")) is int and 0<manifest["captured_at"]<=now and
            pause.get("source_sha")==SOURCE and pause.get("run_id")==str(RUN) and
            type(pause.get("paused_at")) is int and type(pause.get("expires_at")) is int and
            pause["paused_at"]<=manifest["captured_at"]<=pause["expires_at"] and
            index.get("source_restored_after_canary") is True)
        config=json.loads(read("config/bot.json",65536))
        need(config.get("TELEGRAM_OWNER_ID")==owner and
            re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{30,90}",config.get("TELEGRAM_BOT_TOKEN","")))
        token=config["TELEGRAM_BOT_TOKEN"]
        with closing(database(root,"controller.sqlite",read("state/state.sqlite3",16*1024*1024))) as db:
            tasks=table(db,"tasks");updates=table(db,"updates");metadata=table(db,"metadata")
        with closing(database(root,"returns.sqlite",read("state/tf-private-return.sqlite",16*1024*1024))) as db:
            returns=table(db,"deliveries")
        acceptance=[]
        if inventory["acceptance_ledger_present"]:
            with closing(database(root,"acceptance.sqlite",read("state/testflight/acceptance.sqlite",16*1024*1024))) as db:
                acceptance=table(db,"invitations",20)
    stage("tasks")
    scope=hashlib.sha256(("telegram-owner:"+owner).encode()).hexdigest()
    legacy=[];states={}
    for row in tasks:
        need(set(row)=={"scope","rid","app","state","at","created"} and
            re.fullmatch(r"[a-f0-9]{64}",row["scope"]) and
            re.fullmatch(r"(?:cn_|tf_)?[a-f0-9]{32}",row["rid"]) and
            type(row["app"]) is str and row["state"] in ("pending","sending","delivered","closed","cancelled") and
            type(row["at"]) is int and type(row["created"]) is int and 0<=row["created"]<=row["at"]<=now)
        profile="tf" if row["rid"].startswith("tf_") else "cn" if row["rid"].startswith("cn_") else "default"
        states[row["state"]]=states.get(row["state"],0)+1
        legacy.append(dict(owner_id=owner if row["scope"]==scope else "legacy:"+row["scope"],request_id=row["rid"],
            profile=profile,target=row["app"],state=row["state"],created_at=row["created"],
            held=int(row["state"] in ("pending","sending")),source_json=json.dumps(row,sort_keys=True,separators=(",",":"))))
    need(states==inventory["task_states"])
    legacy.sort(key=lambda row:(row["owner_id"],row["request_id"]))
    need(len({(row["owner_id"],row["request_id"]) for row in legacy})==len(legacy))
    stage("updates")
    for row in updates:
        need(set(row)=={"scope","uid","at","done"} and re.fullmatch(r"[a-f0-9]{64}",row["scope"]) and
            type(row["uid"]) is int and row["uid"]>=0 and row["done"] in (0,1) and type(row["at"]) is int)
    stage("metadata")
    for row in metadata:
        need(set(row)=={"scope","name","value"} and re.fullmatch(r"[a-f0-9]{64}",row["scope"]) and
            type(row["name"]) is str and type(row["value"]) is str)
    offsets=[row["value"] for row in metadata if row["scope"]==scope and row["name"]=="offset"]
    need(len(offsets)<=1 and (not offsets or re.fullmatch(r"[0-9]{1,16}",offsets[0])))
    if offsets:need(int(offsets[0])<=9007199254740991)
    browsers=[row["value"] for row in metadata if row["scope"]==scope and row["name"]=="version_browser"]
    need(len(browsers)<=1)
    if browsers:need(type(json.loads(browsers[0])) is dict)
    for row in returns:need(row.get("state") in ("intent","confirmed"))
    for row in acceptance:
        need(set(row)=={"invite","request_id","run_id","source_commit","nonce","expires","state"} and
            row["state"] in ("intent","membership_verified","outcome_unknown"))
    preserved=dict(legacy_tasks=legacy,updates=updates,metadata=metadata,private_returns=returns,acceptance_rows=acceptance)
    encoded=json.dumps(preserved,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    need(len(encoded)<=16*1024*1024)
    result=dict(schema="circleci-offline-recovery-plan-v1",source_run=RUN,source_sha=SOURCE,
        snapshot_sha256=DIGEST,session_sha256=PROMOTED,captured_at=manifest["captured_at"],owner_id=owner,
        source_frozen_at_capture=True,source_currently_frozen=False,source_restored_after_capture=True,
        source_unavailable=True,recovery_gap_unresolved=True,automatic_replay=False,permanent_handoff=False,
        source_disabled_verified=False,telegram_isolation_verified=False,new_update_floor=None,
        old_bot_id=token.split(":")[0],old_token_sha256=hashlib.sha256(token.encode()).hexdigest(),
        retained_records_sha256=hashlib.sha256(encoded).hexdigest(),records=preserved,
        telegram_files={k:v for k,v in manifest["files"].items() if k.startswith("state/telegram/")},
        requires_historical_tf_reconstruction=not inventory["acceptance_ledger_present"],
        source_snapshot_offset=int(offsets[0]) if offsets else None)
    proof=dict(schema="circleci-offline-recovery-proof-v1",source_run=RUN,archive_authenticated=True,
        frozen_at_capture=True,permanent_handoff=False,source_disabled_verified=False,
        telegram_isolation_verified=False,recovery_gap_unresolved=True,automatic_replay=False,
        legacy_rows=len(legacy),held_rows=sum(row["held"] for row in legacy),task_states=states,
        update_rows=len(updates),unfinished_updates=sum(row["done"]!=1 for row in updates),
        metadata_rows=len(metadata),owner_offset_preserved=bool(offsets),owner_browser_preserved=bool(browsers),
        telegram_files=len(result["telegram_files"]),private_return_rows=len(returns),
        private_return_unknown=sum(row["state"]=="intent" for row in returns),
        acceptance_ledger_present=inventory["acceptance_ledger_present"],acceptance_rows=len(acceptance),
        source_modified=False,apple_operation=False,telegram_send=False)
    if token_probe:
        stage("replacement_token")
        fencing=token_probe(token)
        need(type(fencing) is dict and set(fencing)=={"old_token_rejected","replacement_same_bot_verified","replacement_token_sha256"} and
            fencing["old_token_rejected"] is True and fencing["replacement_same_bot_verified"] is True and
            re.fullmatch(r"[a-f0-9]{64}",fencing["replacement_token_sha256"]))
        result.update(fencing)
        proof.update(old_token_rejected=True,replacement_same_bot_verified=True)
    else:
        proof.update(old_token_rejected=False,replacement_same_bot_verified=False)
    return result,proof

def bot_identity(token,execute=None):
    need(type(token) is str and re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{30,90}",token))
    request=urllib.request.Request("https://api.telegram.org/bot"+token+"/getMe",
        headers={"User-Agent":"ipa-offline-recovery/0.2","Accept":"application/json"})
    client=execute or urllib.request.build_opener(NoRedirect()).open
    try:
        with client(request,timeout=15) as response:
            code=response.status;raw=response.read(16385)
    except urllib.error.HTTPError as error:
        code=error.code;raw=error.read(16385)
    need(len(raw)<=16384)
    value=json.loads(raw);need(type(value) is dict)
    return code,value

def verify_replacement(old,new,execute=None):
    need(type(old) is str and type(new) is str and old!=new and old.split(":")[0]==new.split(":")[0])
    code,value=bot_identity(new,execute)
    need(code==200 and value.get("ok") is True and value.get("result",{}).get("is_bot") is True and
        type(value.get("result",{}).get("id")) is int and str(value["result"]["id"])==old.split(":")[0])
    code,value=bot_identity(old,execute)
    need(code in (401,404) and value.get("ok") is False and value.get("error_code")==code)
    return dict(old_token_rejected=True,replacement_same_bot_verified=True,
        replacement_token_sha256=hashlib.sha256(new.encode()).hexdigest())

LEGACY_WORKFLOWS=(
    (407064604,"private-delivery.yml"),(411713917,"china-private-delivery.yml"),
    (412609354,"testflight-private-delivery.yml"),(407542960,"version-catalog.yml"),
    (412705779,"china-version-catalog.yml"),
)
def legacy_fence(token,execute=None):
    need(type(token) is str and len(token)>=16)
    client=execute or urllib.request.build_opener(NoRedirect()).open
    def get(path):
        request=urllib.request.Request("https://api.github.com/repos/"+REPO+path,
            headers={"Authorization":"Bearer "+token,"User-Agent":"ipa-offline-recovery/0.2","Accept":"application/vnd.github+json"})
        with client(request,timeout=15) as response:
            need(response.status==200);raw=response.read(2*1024*1024+1);need(len(raw)<=2*1024*1024)
        return json.loads(raw)
    rows=[]
    for identifier,name in LEGACY_WORKFLOWS:
        value=get("/actions/workflows/"+str(identifier))
        need(value.get("id")==identifier and value.get("path")==".github/workflows/"+name and value.get("state")=="disabled_manually")
        runs=get("/actions/workflows/"+str(identifier)+"/runs?per_page=100")
        need(type(runs.get("total_count")) is int and type(runs.get("workflow_runs")) is list and
            0<=runs["total_count"]==len(runs["workflow_runs"])<=100 and
            all(run.get("status")=="completed" for run in runs["workflow_runs"]))
        rows.append(dict(id=identifier,path=value["path"],state=value["state"],active_runs=0))
    return dict(verified_at=int(time.time()),workflows=rows)

def main():
    os.umask(0o077)
    try:
        env=os.environ
        need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==REPO and
            env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_RUN_ATTEMPT")=="1" and
            env.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and env.get("GITHUB_ACTOR_ID")=="246379322")
        stage("reassemble")
        index=json.loads(env[PREFIX+"INDEX"]);cipher=assemble(index,env)
        stage("decrypt")
        compressed=decrypt(cipher,env["DELIVERY_AGE_IDENTITY"],env)
        with tempfile.TemporaryDirectory(prefix="offline-recovery-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder)
            replacement=env.get("MANAGED_TELEGRAM_BOT_TOKEN","")
            probe=(lambda old:verify_replacement(old,replacement)) if replacement else None
            value,proof=plan(compressed,root,env["RUNTIME_OWNER_ID"],index,token_probe=probe)
            proof["replacement_token_present"]=bool(replacement)
            stage("legacy_dispatch_fence")
            fence=legacy_fence(env["GITHUB_READ_TOKEN"])
            value["legacy_dispatch_fence"]=fence
            proof.update(legacy_workflows_disabled=True,legacy_workflow_count=len(fence["workflows"]))
            stage("encrypt_plan")
            child={key:env[key] for key in ("PATH","HOME","LANG") if key in env}
            raw=json.dumps(value,sort_keys=True,ensure_ascii=False).encode()
            need(len(raw)<=1024*1024)
            encrypted=subprocess.run(["age","--encrypt","--recipient",RECIPIENT],input=raw,capture_output=True,timeout=30,env=child)
            need(encrypted.returncode==0 and encrypted.stdout.startswith(b"age-encryption.org/v1\n") and len(encrypted.stdout)<=17*1024*1024)
            restored=decrypt(encrypted.stdout,env["DELIVERY_AGE_IDENTITY"],env)
            need(restored==raw)
            output=Path("offline-recovery-out");output.mkdir(mode=0o700)
            (output/"recovery-plan.json.age").write_bytes(encrypted.stdout)
            proof.update(plan_cipher_sha256=hashlib.sha256(encrypted.stdout).hexdigest(),plan_roundtrip_verified=True,
                source_commit=env["GITHUB_SHA"],workflow_run=env["GITHUB_RUN_ID"])
            (output/"receipt.json").write_text(json.dumps(proof,sort_keys=True)+"\n")
            print(json.dumps(proof,sort_keys=True));return 0
    except Exception:
        print(json.dumps(dict(schema="circleci-offline-recovery-proof-v1",status="offline_recovery_failed",stage=STAGE)),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
