"""Deploy CI-verified staged runtime and prove one managed task; never switches the Telegram entry."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from cloud_inventory import api,WORKER,NoRedirect
from control_cloud import prepared_metadata,multipart
ORIGIN="https://ipazake-free-control-pilot.hahayesadd.workers.dev"
def need(ok,code):
 if not ok:raise ValueError(code)
def call(path,token=None,value=None):
 need(path in ("ready","init","admit-fixture","admit-drive-fixture","status","canary/install","canary/revoke","admit-export","owner-cancel","owner-get","recovery/stage","recovery/seal","recovery/status"),"runtime_cloud_endpoint")
 headers={"User-Agent":"ipa-decrypt-managed-deployer/0.2","Accept":"application/json"}
 if token:headers["X-Ipazake-Control-Token"]=token
 if value is not None:
  headers["X-Ipazake-Source-Sha"]=os.environ["GITHUB_SHA"]
  value=dict(value,_source=os.environ["GITHUB_SHA"])
 raw=None if value is None else json.dumps(value).encode()
 if raw is not None:headers["Content-Type"]="application/json"
 request=urllib.request.Request(ORIGIN+"/v2/runtime/"+path,data=raw,headers=headers)
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=25) as response:
   need(response.status==200,"runtime_cloud_response");raw=response.read(65537);need(len(raw)<=65536,"runtime_cloud_limit")
 except urllib.error.HTTPError as error:
  code="runtime_cloud_http_"+str(error.code)
  try:
   detail=json.loads(error.read(4096)).get("code","")
   if re.fullmatch(r"[a-z_]{1,60}",detail):code+="_"+detail
  except Exception:pass
  raise ValueError(code) from None
 value=json.loads(raw);need(value.get("ok") is True,"runtime_cloud_response");return value
def deploy(bundle,drive_fixture=False,prepare_only=False):
 env=os.environ
 need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab" and
  env.get("GITHUB_REF")=="refs/heads/upgrade/managed-runtime-v0.2","runtime_cloud_context")
 source=env["GITHUB_SHA"];need(re.fullmatch(r"[a-f0-9]{40}",source),"runtime_cloud_source")
 account,token=env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"]
 circle,github,owner=env["CIRCLECI_API_TOKEN"],env["RUNTIME_GH_TOKEN"],env["RUNTIME_OWNER_ID"]
 need(len(circle)>=16 and len(github)>=16 and re.fullmatch(r"[1-9][0-9]{0,15}",owner),"runtime_cloud_credentials")
 bundle=Path(bundle);raw=bundle.read_bytes()
 need((bundle.parent/"BUILDINFO").read_text()=="source_commit="+source+"\n" and 0<len(raw)<=524288,"runtime_cloud_bundle")
 path="/workers/scripts/"+WORKER
 before=api(account,token,path+"/settings");old={x["name"]:x for x in before["bindings"]}
 need(old.get("RUNTIME_MODE",{}).get("text")!="production","runtime_live_deployment_refused")
 if "RUNTIME_MODE" in old:
  for attempt in range(31):
   readiness=call("ready")
   if readiness.get("source_sha")==old.get("RUNTIME_SOURCE_SHA",{}).get("text") and readiness.get("active") is False:break
   if attempt==30:raise ValueError("runtime_active_deployment_refused")
   time.sleep(10)
 need(api(account,token,path+"/subdomain").get("enabled") is True,"runtime_existing_endpoint_required")
 subdomain=api(account,token,"/workers/subdomain").get("subdomain")
 need(ORIGIN=="https://"+WORKER+"."+str(subdomain)+".workers.dev","runtime_cloud_origin")
 metadata=prepared_metadata(before,source,ORIGIN)
 values=dict(RUNTIME_MODE="staging",RUNTIME_SOURCE_SHA=source,RUNTIME_CONTROL_ORIGIN=ORIGIN)
 metadata["bindings"]=[x for x in metadata["bindings"] if x.get("name") not in values]+[
  dict(type="plain_text",name=k,text=v) for k,v in values.items()]
 receipt=dict(schema="circleci-managed-runtime-cloud-proof-v1",source_sha=source,production=False,
  apple_operation=False,file_upload=False,telegram_send=False,status="preflight",bundle_sha256=hashlib.sha256(raw).hexdigest())
 def save():
  Path("managed-runtime-cloud-proof.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
  print(json.dumps(receipt,sort_keys=True),flush=True)
 save()
 content,kind=multipart(metadata,raw);api(account,token,path,content,method="PUT",content_type=kind)
 control=secrets.token_urlsafe(48)
 for name,value in (("CIRCLECI_API_TOKEN",circle),("RUNTIME_OWNER_ID",owner),
  ("RUNTIME_GH_TOKEN",github),("CIRCLECI_CONTROL_TOKEN",control)):
  api(account,token,path+"/secrets",dict(name=name,type="secret_text",text=value),method="PUT")
 after=api(account,token,path+"/settings");bindings={x["name"]:x for x in after["bindings"]}
 need(bindings.get("DB",{}).get("id")==old.get("DB",{}).get("id") and
  {x["name"] for x in before["bindings"] if x.get("type")=="secret_text"}<=
  {x["name"] for x in after["bindings"] if x.get("type")=="secret_text"},"runtime_existing_bindings_changed")
 for name in ("PILOT_ENABLED","PILOT_LINK_ENABLED"):
  need(bindings.get(name)==old.get(name),"runtime_telegram_flags_changed")
 for name,value in values.items():need(bindings.get(name,{}).get("text")==value,"runtime_source_binding")
 receipt["status"]="deployed_bindings_preserved";save()
 for attempt in range(30):
  try:
   initialized=call("init",control,{})
   if initialized.get("source_sha")==source:break
  except ValueError as error:
   if not any(x in str(error) for x in ("runtime_admin_authentication","http_503","http_404","runtime_fields","runtime_source_not_ready")):raise
  time.sleep(2)
 else:raise ValueError("runtime_deployment_not_ready")
 if prepare_only:return dict(control_token=control,source_sha=source)
 probe=secrets.token_hex(16);job="pilot_"+probe;receipt.update(status="admitted_once",job_id=job);save()
 # Reuse the same logical ID only; the durable dispatch CAS permits one external POST.
 for attempt in range(30):
  try:
   admitted=call("admit-drive-fixture" if drive_fixture else "admit-fixture",control,dict(probe_id=probe))
   need(admitted.get("job_id")==job,"runtime_admission_binding")
   receipt.update(run_id=admitted.get("run_id"));save()
   break
  except (ValueError,urllib.error.URLError,TimeoutError):
   if attempt==29:raise
   time.sleep(2)
 deadline=time.monotonic()+900
 while time.monotonic()<deadline:
  try:
   status=call("status",control,dict(job_id=job))
  except ValueError as error:
   if "runtime_provider_pending" not in str(error):raise
   time.sleep(3);continue
  if status.get("state")=="completed":
   need(status.get("fixture_verified") is True and status.get("ciphertext_cleared") is True and
    re.fullmatch(r"[1-9][0-9]{0,19}",status.get("publisher_run_id") or "") and
    re.fullmatch(r"[a-f0-9]{64}",status.get("cipher_sha256") or ""),"runtime_completion_proof")
   if drive_fixture:need(status.get("drive_fixture") is True and status.get("drive_uploaded") is True and status.get("fixture_cleaned") is True,"runtime_drive_fixture_unconfirmed")
   receipt.update(file_upload=drive_fixture,fixture_cleaned=status.get("fixture_cleaned") is True,decryption_proven=False)
   receipt.update(status="verified",managed_task_verified=True,publisher_identity_verified=True,
    ciphertext_cleared=True,publisher_run_id=status["publisher_run_id"],run_id=status["run_id"],
    cipher_sha256=status["cipher_sha256"]);save();return
  if status.get("state") in ("closed","dispatch_unknown"):
   raise ValueError("runtime_task_unconfirmed_no_retry")
  time.sleep(10)
 raise ValueError("runtime_task_pending_no_retry")
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--bundle",required=True);parser.add_argument("--drive-fixture",action="store_true");args=parser.parse_args()
 try:deploy(args.bundle,args.drive_fixture);return 0
 except Exception as error:
  code=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z0-9_]+",str(error)) else "managed_runtime_cloud_failed"
  print(code,file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
