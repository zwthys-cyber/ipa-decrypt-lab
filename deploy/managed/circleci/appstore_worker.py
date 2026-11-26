"""Default/CN CircleCI adapters; saved models, exact versions, private subprocesses and ciphertext only."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from task_context import validate, credentials, minimal_env, require
from verified_export import export_original, model_bytes
from private_process import run as private_run
from app_preflight import check_app
from private_export import check_capacity
from native_store import authenticate, classify, classify_download
from version_request import resolved_marker
from capacity import DOWNLOAD_TIMEOUT
import cn_profile
import fetch_runtime

def export_task(task,values,output,env=None,checkpoint=lambda stage:None,
                load_runtime=fetch_runtime.fetch,execute=private_run,delivery=None):
    env=os.environ if env is None else env
    task=validate(task,env)
    require(task["profile"] in ("default","cn"),"appstore_profile_required")
    values=credentials(task["profile"],values)
    model_bytes(values["FAIRPLAY_MODEL_B64" if task["profile"]=="default" else "FAIRPLAY_CN_MODEL_B64"])
    if task["profile"]=="cn":cn_profile.decode(values)
    output=Path(output).absolute()
    require(not output.exists() and not output.is_symlink(),"export_destination")
    age=shutil.which("age",path=env.get("PATH"))
    require(age and Path(age).is_absolute(),"age_runtime_missing")
    def stage(name):
        require(int(time.time())<task["deadline"],"task_deadline")
        checkpoint(name)
    stage("metadata")
    info=check_app(task["target"],historical=bool(task["version"]),profile=task["profile"])
    check_capacity({} if task["version"] else info,output.parent)
    repo=Path(__file__).resolve().parents[3]
    pins=json.loads(Path(__file__).with_name("runtime-pins.json").read_text())
    with tempfile.TemporaryDirectory(prefix="circle-private-export-") as folder:
        root=Path(folder);root.chmod(0o700)
        runtime=root/"runtime";home=root/"home";home.mkdir(mode=0o700)
        stage("loading_runtime")
        loaded=load_runtime(repo,pins,"base" if task["profile"]=="default" else "cn",runtime)
        require(loaded.get("schema")=="circleci-native-fetch-v1" and loaded.get("source")==pins["source"] and
            loaded.get("variant")==("base" if task["profile"]=="default" else "cn") and
            loaded.get("archive_sha256")==pins["variants"][loaded.get("variant", "")]["archive_sha256"],
            "runtime_fetch_proof")
        binary,helper,engine=(runtime/x for x in ("ApplePackageTool","lab-kbsync","offline-engine"))
        def run(binary,args,child,timeout=300):
            remaining=task["deadline"]-int(time.time())
            return execute(binary,args,child,min(timeout,remaining),root,lambda:stage("working"))
        child=minimal_env(env,home);child["LAB_KBSYNC_HELPER"]=str(helper)
        stage("preparing_public_resources")
        require(run(helper,["--prewarm"],minimal_env(env,home),240).returncode==0,"public_assets_unavailable")
        original=root/"source.ipa"
        def download(email,child,guid=None):
            child=dict(child)
            if task["version"]:child["LAB_REQUESTED_VERSION"]=task["version"]
            args=["download",email,info["bundleId"],"--output",original]
            if guid:args+=["--guid",guid]
            stage("resolving_version" if task["version"] else "downloading")
            result=run(binary,args,child,DOWNLOAD_TIMEOUT)
            require(result.returncode==0 and original.is_file(),
                "version_download_rejected" if task["version"] else classify_download(result))
            return resolved_marker(result.stdout or "",task["version"]) if task["version"] else ("","")
        staged=root/"sealed-out"
        if task["profile"]=="default":
            email=values["APPLE_ID"].strip();require(email,"apple_identity_missing")
            login=dict(child,APPLEPACKAGE_PASSWORD=values["APPLE_PASSWORD"])
            stage("authenticating")
            try:
                result=authenticate(binary,["login",email],login,execute=run,on_retry=lambda:stage("auth_retry"))
                require(classify(result)=="authenticated","apple_authentication_rejected")
                version_id,resolved=download(email,child)
                receipt=export_original(task,engine,age,root,original,info,values["FAIRPLAY_MODEL_B64"],staged,
                    env,run,stage,version_id,resolved,delivery=delivery)
            finally:
                try:run(binary,["logout",email],child,30)
                except Exception:pass
        else:
            stage("authenticating")
            with cn_profile.saved_session(binary,helper,values,env,home,run) as (account,child,path):
                version_id,resolved=download(account["email"],child,account["guid"])
                cn_profile.bound(path,account,values)
                receipt=export_original(task,engine,age,root,original,info,values["FAIRPLAY_CN_MODEL_B64"],staged,
                    env,run,stage,version_id,resolved,delivery=delivery)
        stage("finalizing_ciphertext")
        require(not output.exists() and not output.is_symlink(),"export_destination")
        staged.rename(output)
        try:stage("artifact_ready")
        except BaseException:
            shutil.rmtree(output,ignore_errors=True)
            raise
        return receipt
