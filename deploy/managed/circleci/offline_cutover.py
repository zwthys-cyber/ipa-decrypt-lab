"""Owner-only GitHub offline cutover. No Apple tasks, old replay or old VPS access."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tarfile
import tempfile
import time
import urllib.request
from cloud_inventory import api,WORKER,NoRedirect
from control_cloud import prepared_metadata,multipart
from runtime_cloud import deploy,call,ORIGIN
from retain_canary_archive import PREFIX,assemble,REPO,BRANCH
from read_preserved import decrypt
from offline_recovery import plan,verify_replacement,legacy_fence

STAGE="context"
def stage(name):
 global STAGE
 STAGE=name
def need(ok,code="offline_cutover_invalid"):
 if not ok:raise ValueError(code)
def public(env):return {k:env[k] for k in ("PATH","HOME","LANG") if k in env}
def bot(method,token,body=None):
 need(method in ("setWebhook","getWebhookInfo"),"offline_bot_method")
 need(re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{30,90}",token),"offline_bot_token")
 raw=None if body is None else json.dumps(body).encode()
 req=urllib.request.Request("https://api.telegram.org/bot"+token+"/"+method,data=raw,
  headers={"Content-Type":"application/json","User-Agent":"ipa-offline-cutover/0.2"})
 with urllib.request.build_opener(NoRedirect()).open(req,timeout=25) as r:
  value=r.read(16385);need(r.status==200 and len(value)<=16384,"offline_bot_response")
 value=json.loads(value);need(value.get("ok") is True,"offline_bot_response");return value["result"]
def mode(bundle,env,enabled):
 path="/workers/scripts/"+WORKER
 before=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path+"/settings")
 metadata=prepared_metadata(before,env["GITHUB_SHA"],ORIGIN)
 values=dict(RUNTIME_MODE="production" if enabled else "staging",RUNTIME_EXPORT_ENABLED="1" if enabled else "0",
  RUNTIME_TELEGRAM_ENABLED="1" if enabled else "0",RUNTIME_BILLING_ENABLED="0")
 metadata["bindings"]=[x for x in metadata["bindings"] if x.get("name") not in values]+[
  dict(type="plain_text",name=k,text=v) for k,v in values.items()]
 body,kind=multipart(metadata,Path(bundle).read_bytes())
 api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path,body,method="PUT",content_type=kind)
 after=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path+"/settings")
 actual={x["name"]:x for x in after["bindings"]}
 need(all(actual.get(k,{}).get("text")==v for k,v in values.items()),"offline_mode_unconfirmed")
 need(next(x for x in after["bindings"] if x["name"]=="DB")==next(x for x in before["bindings"] if x["name"]=="DB"),"offline_database_changed")
def put_secret(env,name,value):
 need(name in ("TELEGRAM_BOT_TOKEN","TELEGRAM_WEBHOOK_SECRET","RUNTIME_TF_HMAC_KEY"),"offline_secret_scope")
 api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],"/workers/scripts/"+WORKER+"/secrets",
  dict(name=name,type="secret_text",text=value),method="PUT")
def warm_call(path,control,value):
 for attempt in range(30):
  try:return call(path,control,value)
  except ValueError as error:
   if not any(s in str(error) for s in ("runtime_source_not_ready","runtime_admin_authentication","runtime_fields","http_503","http_404")) or attempt==29:raise
   time.sleep(2)
def history(env):
 sys.path.insert(0,str(Path(__file__).resolve().parents[3]/".github/ops"))
 import tf_history_recovery as tf
 packet=tf.collect()
 plain=decrypt(base64.b64decode(packet["ciphertext_b64"],validate=True),env["DELIVERY_AGE_IDENTITY"],env)
 tf.packet_valid(packet,json.loads(plain))
 return True
def schedules(env):
 path="/workers/scripts/"+WORKER+"/schedules"
 before=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path)
 need(type(before) is dict and type(before.get("schedules")) is list,"offline_cron_inventory")
 cron={row["cron"] for row in before["schedules"]}
 cron.add("* * * * *");need(len(cron)<=3,"offline_cron_limit")
 desired=[dict(cron=value) for value in sorted(cron)]
 api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path,desired,method="PUT")
 after=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path)
 need({r["cron"] for r in after["schedules"]}==cron,"offline_cron_unconfirmed")
def run(bundle):
 env=os.environ
 need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==REPO and
  env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_RUN_ATTEMPT")=="1" and
  env.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and env.get("GITHUB_ACTOR_ID")=="246379322","offline_cutover_context")
 need(re.fullmatch(r"[a-f0-9]{64}",env.get("MANAGED_TF_HMAC_KEY","")),"offline_hmac_missing")
 os.umask(0o077)
 output=Path("offline-cutover-out");output.mkdir(mode=0o700,exist_ok=False)
 proof=dict(schema="circleci-offline-cutover-proof-v1",source_commit=env["GITHUB_SHA"],workflow_run=env["GITHUB_RUN_ID"],
  production_cutover=False,source_disabled_verified=False,recovery_gap_held=True,automatic_replay=False,
  apple_operation=False,file_upload=False,telegram_send=False,status="preflight")
 def save():
  raw=json.dumps(proof,sort_keys=True)+"\n"
  (output/"receipt.json").write_text(raw);print(raw,end="",flush=True)
 deployed=False;activated=False;complete=False
 try:
  stage("backup_and_token")
  index=json.loads(env[PREFIX+"INDEX"]);cipher=assemble(index,env);compressed=decrypt(cipher,env["DELIVERY_AGE_IDENTITY"],env)
  with tempfile.TemporaryDirectory(prefix="offline-handoff-",dir=env["RUNNER_TEMP"]) as folder:
   value,inventory=plan(compressed,Path(folder),env["RUNTIME_OWNER_ID"],index,
    token_probe=lambda old:verify_replacement(old,env["MANAGED_TELEGRAM_BOT_TOKEN"]))
   with tarfile.open(fileobj=io.BytesIO(compressed),mode="r:gz") as archive:
    config=json.loads(archive.extractfile(archive.getmember("config/bot.json")).read(65537))
   old=config["TELEGRAM_BOT_TOKEN"]
   need(hashlib.sha256(old.encode()).hexdigest()==value["old_token_sha256"])
   stage("legacy_fence");fence=legacy_fence(env["GITHUB_READ_TOKEN"])
   stage("historical_tf");confirmed=history(env)
   proof.update(old_token_rejected=True,same_bot_verified=True,legacy_workflows_disabled=True,history_confirmed=True,
    legacy_rows=inventory["legacy_rows"],held_rows=inventory["held_rows"],update_rows=inventory["update_rows"],
    metadata_rows=inventory["metadata_rows"],snapshot_sha256=value["snapshot_sha256"])
   save()
   records=json.dumps(value["records"],sort_keys=True,separators=(",",":"),ensure_ascii=False)
   digest=hashlib.sha256(records.encode()).hexdigest();need(digest==value["retained_records_sha256"])
   stage("disabled_candidate")
   control=deploy(bundle,prepare_only=True)["control_token"];deployed=True
   mode(bundle,env,False)
   before=warm_call("recovery/status",control,{})
   key_hash=hashlib.sha256(env["MANAGED_TF_HMAC_KEY"].encode()).hexdigest()
   need(not before.get("hmac_key_sha256") or before["hmac_key_sha256"]==key_hash,"offline_existing_hmac_conflict")
   if not before.get("hmac_key_sha256"):put_secret(env,"RUNTIME_TF_HMAC_KEY",env["MANAGED_TF_HMAC_KEY"])
   put_secret(env,"TELEGRAM_BOT_TOKEN",env["MANAGED_TELEGRAM_BOT_TOKEN"])
   webhook_secret=secrets.token_urlsafe(48);put_secret(env,"TELEGRAM_WEBHOOK_SECRET",webhook_secret)
   packet=dict(schema="circleci-offline-stage-v1",source_run=value["source_run"],snapshot_sha256=value["snapshot_sha256"],
    records_json=records,records_sha256=digest,captured_at=value["captured_at"],old_token=old,tf_history_verified=confirmed)
   stage("import")
   for attempt in range(30):
    try:
     result=call("recovery/stage",control,dict(packet=packet));need(result.get("staged") is True);break
    except ValueError as error:
     if not any(s in str(error) for s in ("runtime_source_not_ready","runtime_admin_authentication","runtime_recovery_entry_not_closed","runtime_recovery_token","runtime_recovery_hmac","http_503")) or attempt==29:raise
     time.sleep(2)
   state=warm_call("recovery/status",control,{})
   need(state.get("records_readback_verified") is True and state.get("legacy_rows")==29 and state.get("held_rows")==2 and
    state.get("known_delivery_preserved") is True and state.get("token_bound") is True,"offline_import_unconfirmed")
   proof.update(status="imported",known_delivery_preserved=True,records_readback_verified=True);save()
   stage("seal")
   sealed=call("recovery/seal",control,dict(packet=dict(records_sha256=digest,old_token=old)))
   need(sealed.get("sealed") is True)
   stage("cron_install");schedules(env)
   stage("webhook_install")
   # A failed/unknown configuration POST leaves this disabled candidate closed. No job is submitted.
   need(bot("setWebhook",env["MANAGED_TELEGRAM_BOT_TOKEN"],dict(url=ORIGIN+"/telegram",secret_token=webhook_secret,
    max_connections=1,allowed_updates=["message","callback_query"],drop_pending_updates=False)) is True,"offline_webhook_unconfirmed")
   info=bot("getWebhookInfo",env["MANAGED_TELEGRAM_BOT_TOKEN"])
   need(info.get("url")==ORIGIN+"/telegram","offline_webhook_unconfirmed")
   stage("activate");activated=True;mode(bundle,env,True)
   stage("actual_cron_readback")
   deadline=time.monotonic()+900
   while time.monotonic()<deadline:
    state=call("recovery/status",control,{})
    if (state.get("sealed") is True and state.get("tf_sealed") is True and state.get("fence_live") is True and
       type(state.get("last_cron_tick_at")) is int and state["last_cron_tick_at"]>=state["activated_at"]):
     need(state.get("known_delivery_preserved") is True and state.get("records_readback_verified") is True)
     break
    time.sleep(10)
   else:raise ValueError("offline_actual_cron_unconfirmed")
   info=bot("getWebhookInfo",env["MANAGED_TELEGRAM_BOT_TOKEN"])
   need(info.get("url")==ORIGIN+"/telegram","offline_webhook_unconfirmed")
   complete=True
   proof.update(status="verified",production_cutover=True,offline_handoff_sealed=True,tf_historical_tombstone_sealed=True,
    webhook_verified=True,cron_verified=True,last_cron_tick_at=state["last_cron_tick_at"],
    private_legacy_rows=state["legacy_rows"],private_held_rows=state["held_rows"],bot_entry_real_message_verified=False)
   save()
 except BaseException:
  if activated and not complete:
   try:mode(bundle,env,False);proof["entry_reclosed"]=True
   except BaseException:proof["entry_reclose_unknown"]=True
  proof.update(status="incomplete",stage=STAGE);save();raise

def main():
 parser=argparse.ArgumentParser();parser.add_argument("--bundle",required=True);args=parser.parse_args()
 try:run(args.bundle);return 0
 except Exception as error:
  reason=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z0-9_]{1,100}",str(error)) else "offline_cutover_failed"
  print(json.dumps(dict(schema="circleci-offline-cutover-proof-v1",status="failed",stage=STAGE,reason=reason)),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
