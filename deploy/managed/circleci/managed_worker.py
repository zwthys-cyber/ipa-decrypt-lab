"""Bounded CircleCI task client. Staging permits only a pinned project-owned upload fixture."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import threading
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from credential_envelope import context,consumer,open_envelope,public_env
from task_context import validate
import fetch_runtime
TASK_DEADLINE=0
ORIGIN="https://ipazake-free-control-pilot.hahayesadd.workers.dev"
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
def need(ok,code):
 if not ok:raise ValueError(code)
def rpc_once(path,value):
 need(path in ("claim","lease-request","lease-read","finish","plaintext-proof","upload-access","upload-journal","upload-register","fixture-cleanup","checkpoint","lease-consumed","export-finish","worker-failed","tf-permit","catalog-finish"),"managed_endpoint")
 token=os.environ.get("CIRCLE_OIDC_TOKEN_V3","")
 need(token and len(token)<=16384,"managed_identity")
 request=urllib.request.Request(ORIGIN+"/v2/runtime/"+path,data=json.dumps(dict(value,_source=os.environ["MANAGED_SOURCE"])).encode(),method="POST",
  headers={"X-Ipazake-Job-Token":token,"X-Ipazake-Source-Sha":os.environ["MANAGED_SOURCE"],"Content-Type":"application/json","User-Agent":"ipa-decrypt-managed-worker/0.2"})
 try:
  with urllib.request.build_opener(NoRedirect).open(request,timeout=min(25,max(1,TASK_DEADLINE-time.time())) if TASK_DEADLINE else 25) as response:
   need(response.status==200,"managed_response")
   raw=response.read(360001);need(len(raw)<=360000,"managed_response_limit")
 except urllib.error.HTTPError as error:
  code="managed_request_rejected"
  try:
   value=json.loads(error.read(4096))
   if re.fullmatch(r"[a-z_]{1,60}",value.get("code","")):code=value["code"]
  except Exception:pass
  raise ValueError(code) from None
 value=json.loads(raw);need(value.get("ok") is True,"managed_response");return value
def rpc(path,value):
 # Every mutation is keyed by the same committed job/context; external dispatches use durable CAS intents.
 for attempt in range(30):
  if TASK_DEADLINE and time.time()>=TASK_DEADLINE:raise InterruptedError("deadline")
  try:return rpc_once(path,value)
  except ValueError as error:
   warm=("runtime_source_not_ready","runtime_fields","runtime_provider_pending","runtime_job_binding")
   if not any(code in str(error) for code in warm) or attempt==29:raise
  except (urllib.error.URLError,TimeoutError):
   if attempt==29:raise
  time.sleep(2)
 raise ValueError("managed_runtime_not_ready")
def main():
 global TASK_DEADLINE
 env=os.environ
 need(env.get("CIRCLECI")=="true" and not env.get("GITHUB_ACTIONS") and
  env.get("MANAGED_ORIGIN")==ORIGIN and env.get("MANAGED_SOURCE")==env.get("CIRCLE_SHA1") and
  re.fullmatch(r"pilot_[a-f0-9]{32}",env.get("MANAGED_JOB","")),"managed_context")
 identity=dict(job_id=env["MANAGED_JOB"],worker_job_id=env["CIRCLE_WORKFLOW_JOB_ID"])
 result=rpc("claim",identity)
 task=result["task"]
 need(task["run_id"]==env["MANAGED_RUN_ID"] and task["source_sha"]==env["MANAGED_SOURCE"],"managed_run_binding")
 actual_env=dict(env,RUNTIME_RUN_ID=task["run_id"]);validate(task,actual_env)
 TASK_DEADLINE=task["deadline"]
 watchdog=threading.Timer(max(1,TASK_DEADLINE-time.time()),lambda:os.kill(os.getpid(),signal.SIGTERM))
 watchdog.daemon=True;watchdog.start()
 need(result["task_kind"] in ("fixture","export","catalog"),"managed_task_kind")
 fixture_task=result["task_kind"]=="fixture"
 catalog_task=result["task_kind"]=="catalog"
 with tempfile.TemporaryDirectory(prefix="managed-task-") as directory:
  root=Path(directory);root.chmod(0o700)
  repo=Path(__file__).resolve().parents[3]
  pins=json.loads(Path(__file__).with_name("runtime-pins.json").read_text())
  variants=("base",) if fixture_task or task["profile"]=="default" else ("cn","testflight") if task["profile"]=="tf" else ("cn",)
  preloaded={}
  for variant in variants:
   destination=root/("public-"+variant)
   preloaded[variant]=(destination,fetch_runtime.fetch(repo,pins,variant,destination))
  loaded=preloaded[variants[0]][1]
  def load_runtime(unused_repo,unused_pins,variant,output):
   need(variant in preloaded,"managed_runtime_variant")
   path,proof=preloaded[variant];shutil.copytree(path,output);return dict(proof)
  print(json.dumps(dict(stage="public_runtime_verified",job_id=task["job_id"],variant=loaded["variant"])),flush=True)
  key=root/"identity.txt"
  subprocess.run(["age-keygen","-o",str(key)],capture_output=True,check=True,timeout=20,env=public_env(env))
  recipient=subprocess.check_output(["age-keygen","-y",str(key)],text=True,timeout=15,env=public_env(env)).strip()
  expected=context(dict(schema="circleci-credential-request-v1",job_id=task["job_id"],run_id=task["run_id"],
   worker_job_id=task["worker_job_id"],source_sha=task["source_sha"],profile="synthetic" if fixture_task else task["profile"]+("_catalog" if catalog_task else ""),recipient=recipient,
   nonce=os.urandom(16).hex(),expires_at=int(time.time())+600))
  consumer(actual_env,expected)
  answer=rpc("lease-request",dict(identity,recipient=recipient,nonce=expected["nonce"],expires_at=expected["expires_at"]))
  need(answer.get("context")==expected,"managed_lease_binding")
  deadline=time.monotonic()+540;last_print=0
  while time.monotonic()<deadline:
   answer=rpc("lease-read",identity)
   if answer.get("ciphertext"):
    need(answer.get("context")==expected,"managed_lease_binding")
    cipher=base64.b64decode(answer["ciphertext"],validate=True)
    digest=hashlib.sha256(cipher).hexdigest()
    need(digest==answer.get("cipher_sha256"),"managed_lease_digest")
    values=open_envelope(cipher,key,expected,actual_env)
    if fixture_task:need(values=={"fixture":"synthetic-private-fixture"},"managed_fixture")
    break
   if time.monotonic()-last_print>=30:
    print(json.dumps(dict(stage="waiting_for_credentials",job_id=task["job_id"])),flush=True);last_print=time.monotonic()
   time.sleep(3)
  else:raise ValueError("managed_lease_timed_out")
  rpc("lease-consumed",identity)
  uploaded=False;cleaned=False
  real_receipt=None
  if catalog_task:
   from runtime_execution import execute_catalog
   catalog_receipt=execute_catalog(task,values,result["catalog_before"],actual_env,rpc,load_runtime)
  if not fixture_task and not catalog_task:
   from runtime_execution import execute_export
   real_receipt=execute_export(task,values,root,actual_env,rpc,ORIGIN,load_runtime)
   uploaded=True
  if result.get("drive_fixture") is True:
   from runtime_uploader import deliver
   binding=result["fixture_binding"]
   need(binding["producer_source"]==pins["source"] and binding["producer_job"]==pins["job_number"] and
    binding["producer_workflow"]==pins["workflow_id"],"managed_fixture_producer")
   endpoint=fetch_runtime.trusted_job(pins)
   matches=[item for item in fetch_runtime.api(endpoint)["items"] if item.get("path")==binding["path"]]
   need(len(matches)==1,"managed_fixture_artifact")
   sample=root/"fixture.ipa";fetch_runtime.download(matches[0]["url"],sample,binding["sha256"])
   need(sample.stat().st_size==binding["bytes"],"managed_fixture_size");sample.chmod(0o600)
   def checkpoint():
    need(int(time.time())<task["deadline"],"managed_task_expired")
   fixture=dict(schema="circleci-private-upload-fixture-v1",job_id=task["job_id"],run_id=task["run_id"],
    worker_job_id=task["worker_job_id"],source_commit=task["source_sha"],fixture_authorized=True,
    decryption_proven=False,plaintext_verified=False,account_data_removed=False,archive_verified=True,
    plaintext_sha256=binding["sha256"],plaintext_bytes=binding["bytes"],filename=binding["filename"])
   # validate_file inside deliver reads every member CRC and the complete SHA before any Drive creation.
   deliver(sample,fixture,rpc,identity,ORIGIN,checkpoint,fixture=True);uploaded=True
   cleaned=rpc("fixture-cleanup",identity).get("cleaned") is True
   need(cleaned,"managed_fixture_cleanup")
  if fixture_task:rpc("finish",dict(identity,fixture_verified=True))
  proof=dict(schema="circleci-managed-task-proof-v1",job_id=task["job_id"],source_sha=task["source_sha"],
   run_id=task["run_id"],worker_job_id=task["worker_job_id"],fixture_verified=fixture_task,cipher_sha256=digest,
   production=not fixture_task,apple_operation=not fixture_task,file_upload=uploaded,fixture_cleaned=cleaned,decryption_proven=not fixture_task and not catalog_task,telegram_send=False)
  if catalog_task:
   proof.update(task_kind="catalog",catalog_rows=len(catalog_receipt["rows"]),
    telegram_send=catalog_receipt.get("_notification_confirmed") is True)
  if real_receipt is not None:
   proof.update(encrypted_images=real_receipt["encrypted_images"],decrypted_pages=real_receipt["decrypted_pages"],
    plaintext_bytes=real_receipt["plaintext_bytes"],telegram_send=real_receipt.get("_notification_confirmed") is True)
  out=Path("managed-runtime-out");out.mkdir(mode=0o700,exist_ok=True)
  (out/"receipt.json").write_text(json.dumps(proof,sort_keys=True)+"\n")
  print(json.dumps(proof,sort_keys=True),flush=True)
def entry():
 def stop(*unused):raise InterruptedError()
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 try:main();return 0
 except BaseException as error:
  try:
   if (not TASK_DEADLINE or time.time()<TASK_DEADLINE-3) and re.fullmatch(r"pilot_[a-f0-9]{32}",os.environ.get("MANAGED_JOB","")):
    rpc("worker-failed",dict(job_id=os.environ["MANAGED_JOB"],worker_job_id=os.environ["CIRCLE_WORKFLOW_JOB_ID"]))
  except BaseException:pass
  code=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z_]{1,60}",str(error)) else "managed_worker_failed"
  print(code,file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(entry())
