"""CircleCI historical metadata adapter; no model, package export or delivery credentials."""
import json
import os
from pathlib import Path
import re
import tempfile
import time
from task_context import validate, credentials, minimal_env, require
from private_process import run as private_run
from app_preflight import check_app
from native_store import authenticate, classify
from version_catalog_worker import parse_page
import cn_profile
import fetch_runtime

def query_catalog(task,values,before="",env=None,checkpoint=lambda stage:None,
                  load_runtime=fetch_runtime.fetch,execute=private_run):
    env=os.environ if env is None else env
    task=validate(task,env)
    require(task["profile"] in ("default","cn") and not task["version"],"catalog_task")
    require(type(before) is str and (not before or re.fullmatch(r"[1-9][0-9]{5,19}",before)),"catalog_cursor")
    values=credentials(task["profile"]+"_catalog",values)
    if task["profile"]=="cn":cn_profile.decode_session(values)
    def stage(name):
        require(int(time.time())<task["deadline"],"task_deadline")
        checkpoint(name)
    stage("metadata")
    info=check_app(task["target"],historical=True,profile=task["profile"])
    repo=Path(__file__).resolve().parents[3]
    pins=json.loads(Path(__file__).with_name("runtime-pins.json").read_text())
    variant="base" if task["profile"]=="default" else "cn"
    with tempfile.TemporaryDirectory(prefix="circle-private-catalog-") as folder:
        root=Path(folder);root.chmod(0o700)
        runtime=root/"runtime";home=root/"home";home.mkdir(mode=0o700)
        stage("loading_runtime")
        loaded=load_runtime(repo,pins,variant,runtime)
        require(loaded.get("schema")=="circleci-native-fetch-v1" and loaded.get("source")==pins["source"] and
            loaded.get("variant")==variant and loaded.get("archive_sha256")==pins["variants"][variant]["archive_sha256"],
            "runtime_fetch_proof")
        binary,helper=(runtime/name for name in ("ApplePackageTool","lab-kbsync"))
        def run(binary,args,child,timeout=300):
            stage("working")
            remaining=task["deadline"]-int(time.time())
            require(remaining>0,"task_deadline")
            return execute(binary,args,child,min(timeout,remaining),root,lambda:stage("working"))
        child=minimal_env(env,home);child["LAB_KBSYNC_HELPER"]=str(helper)
        stage("preparing_public_resources")
        warm=minimal_env(env,home);warm["LAB_KBSYNC_CHILD"]="1"
        require(run(helper,["--prewarm"],warm,240).returncode==0,"public_assets_unavailable")
        def query(email,child,guid=None):
            query_env=dict(child,LAB_VERSION_CATALOG="1",LAB_CATALOG_BEFORE=before,LAB_CATALOG_PAGED="1")
            destination=root/"unused.ipa"
            args=["download",email,info["bundleId"],"--output",destination]
            if guid:args+=["--guid",guid]
            stage("catalog_query")
            result=run(binary,args,query_env,300)
            require(result.returncode==0 and not destination.exists() and not destination.is_symlink() and
                not any(root.rglob("*.ipa")),"catalog_query_failed")
            return parse_page(result.stdout or "",before)
        stage("authenticating")
        if task["profile"]=="default":
            email=values["APPLE_ID"].strip();require(email,"apple_identity_missing")
            try:
                result=authenticate(binary,["login",email],dict(child,APPLEPACKAGE_PASSWORD=values["APPLE_PASSWORD"]),
                    execute=run,on_retry=lambda:stage("auth_retry"))
                require(classify(result)=="authenticated","catalog_authentication_failed")
                total,rows,next_before=query(email,child)
            finally:
                try:run(binary,["logout",email],child,30)
                except Exception:pass
        else:
            with cn_profile.saved_session(binary,helper,values,env,home,run,metadata_only=True) as (account,child,path):
                total,rows,next_before=query(account["email"],child,account["guid"])
        stage("catalog_ready")
        return dict(schema="circleci-version-catalog-v1",job_id=task["job_id"],request_id=task["request_id"],
            run_id=task["run_id"],worker_job_id=task["worker_job_id"],source_sha=task["source_sha"],
            account_profile=task["profile"],app_id=task["target"],before=before,next_before=next_before,
            total=total,rows=rows)
