"""Block production promotion until current-source runtimes and a no-send TF export are verified."""
import json
import os
from pathlib import Path
import re
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from telegram_queue import GitHub
from native_runtime import fingerprint as native_fingerprint
from cn_runtime import fingerprint as cn_fingerprint
from tf_task_runtime import fingerprint as tf_fingerprint
from tf_task_contract import fingerprint as contract_fingerprint

def artifact_run(api,name,workflow):
    items=api.call("/actions/artifacts?per_page=20&name="+name).get("artifacts",[])
    for item in items:
        if item.get("name")!=name or item.get("expired") is not False or not re.fullmatch("sha256:[a-f0-9]{64}",item.get("digest","")):continue
        bound=item.get("workflow_run",{});run=api.call("/actions/runs/"+str(bound.get("id")))
        if run.get("path")==workflow and run.get("head_branch")=="main" and run.get("status")=="completed" and run.get("conclusion")=="success" and run.get("head_sha")==bound.get("head_sha"):
            return run["id"]
    return None
def tf_runtime_run(api,stamp):
    runs=api.call("/actions/workflows/testflight-runtime-build.yml/runs?status=success&branch=main&per_page=10").get("workflow_runs",[])
    for run in runs:
        if run.get("path")!=".github/workflows/testflight-runtime-build.yml" or run.get("head_branch")!="main" or run.get("conclusion")!="success":continue
        items=api.call("/actions/runs/"+str(run["id"])+"/artifacts?per_page=100").get("artifacts",[])
        for item in items:
            if (item.get("expired") is False and re.fullmatch("tf-public-runtime-"+stamp+"-[a-f0-9]{64}",item.get("name",""))
                    and re.fullmatch("sha256:[a-f0-9]{64}",item.get("digest",""))):
                return run["id"]
    return None
def ready(api):
    native=native_fingerprint(Path("."));cn=cn_fingerprint(Path("."));tf=tf_fingerprint();contract=contract_fingerprint()
    producers={}
    for pool in ("macos-26-intel","macos-15-intel"):
        producers[pool]=artifact_run(api,"runtime-"+pool+"-"+native,".github/workflows/native-runtime-build.yml")
    producers["cn"]=artifact_run(api,"cn-auth-runtime-macos-26-intel-"+cn,".github/workflows/cn-auth-runtime.yml")
    producers["tf"]=tf_runtime_run(api,tf)
    producers["tf_export"]=artifact_run(api,"tf-export-proof-"+contract,".github/workflows/testflight-export-smoke.yml")
    return producers if all(producers.values()) else None
def main():
    api=GitHub(os.environ["GH_TOKEN"])
    for attempt in range(60):
        value=None
        try:value=ready(api)
        except Exception:pass
        if value:
            print(json.dumps({"schema":"tf-production-readiness-v1","ready":True,"producers":value}),flush=True);return 0
        print(json.dumps({"schema":"tf-production-readiness-v1","ready":False,"poll":attempt+1}),flush=True)
        time.sleep(30)
    return 2
if __name__=="__main__":raise SystemExit(main())
