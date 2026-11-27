"""Owner-only maintenance closure using the exact existing live source and tested bundle."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from cloud_inventory import api,WORKER,NoRedirect
from control_cloud import prepared_metadata,multipart
from runtime_cloud import ORIGIN
BRANCH="upgrade/managed-runtime-maintenance-v0.2"
def need(ok,code):
 if not ok:raise ValueError(code)
def public(path,body=None):
 need(path in ("ready","telegram"),"maintenance_endpoint")
 url=ORIGIN+("/v2/runtime/ready" if path=="ready" else "/telegram")
 request=urllib.request.Request(url,data=None if body is None else json.dumps(body).encode(),
  headers={"User-Agent":"ipa-controlled-maintenance/0.2","Content-Type":"application/json"})
 try:
  with urllib.request.build_opener(NoRedirect()).open(request,timeout=20) as r:return r.status,json.loads(r.read(4096))
 except urllib.error.HTTPError as error:return error.code,{}
def close(bundle,expected,env=None):
 env=os.environ if env is None else env
 need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")=="zwthys-cyber/ipa-decrypt-lab" and
  env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_EVENT_NAME")=="workflow_dispatch" and
  env.get("GITHUB_RUN_ATTEMPT")=="1" and env.get("GITHUB_ACTOR_ID")=="246379322","maintenance_context")
 need(re.fullmatch(r"[a-f0-9]{40}",expected),"maintenance_source")
 bundle=Path(bundle);raw=bundle.read_bytes()
 need(0<len(raw)<=524288 and (bundle.parent/"BUILDINFO").read_text()=="source_commit="+expected+"\n","maintenance_bundle")
 path="/workers/scripts/"+WORKER
 before=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path+"/settings")
 bindings={x["name"]:x for x in before["bindings"]}
 need(bindings.get("RUNTIME_SOURCE_SHA",{}).get("text")==expected and
  bindings.get("RUNTIME_MODE",{}).get("text") in ("production","staging"),"maintenance_live_source_changed")
 code,ready=public("ready")
 need(code==200 and ready.get("source_sha")==expected and ready.get("active") is False,"maintenance_active_tasks")
 metadata=prepared_metadata(before,expected,ORIGIN)
 values=dict(RUNTIME_MODE="staging",RUNTIME_EXPORT_ENABLED="0",RUNTIME_TELEGRAM_ENABLED="0",RUNTIME_BILLING_ENABLED="0")
 metadata["bindings"]=[x for x in metadata["bindings"] if x.get("name") not in values]+[
  dict(type="plain_text",name=k,text=v) for k,v in values.items()]
 body,kind=multipart(metadata,raw)
 api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path,body,method="PUT",content_type=kind)
 for attempt in range(45):
  after=api(env["CF_ACCOUNT_ID"],env["CF_API_TOKEN"],path+"/settings");current={x["name"]:x for x in after["bindings"]}
  need(current.get("DB")==bindings.get("DB") and current.get("RUNTIME_SOURCE_SHA")==bindings.get("RUNTIME_SOURCE_SHA"),"maintenance_bindings_changed")
  closed=all(current.get(k,{}).get("text")==v for k,v in values.items())
  code,unused=public("telegram",{})
  if closed and code==503:break
  time.sleep(2)
 else:raise ValueError("maintenance_closure_unconfirmed")
 code,ready=public("ready")
 need(code==200 and ready.get("source_sha")==expected and ready.get("active") is False,"maintenance_active_tasks_after_close")
 proof=dict(schema="circleci-maintenance-closure-v1",entry_closed=True,source_unchanged=True,source_sha=expected,
  database_preserved=True,no_active_tasks=True,bundle_sha256=hashlib.sha256(raw).hexdigest(),apple_operation=False,telegram_send=False)
 Path("maintenance-closure.json").write_text(json.dumps(proof,sort_keys=True)+"\n")
 print(json.dumps(proof,sort_keys=True));return proof
def main():
 try:close("live-control/worker.mjs",os.environ["EXPECTED_SOURCE"]);return 0
 except Exception as error:
  reason=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z0-9_]{1,80}",str(error)) else "maintenance_closure_failed"
  print(reason);return 2
if __name__=="__main__":raise SystemExit(main())
