"""CircleCI TF adapter: original virtual identity, fixed saved session and durable permit callback."""
import base64
import json
import os
from pathlib import Path
import plistlib
import shutil
import sys
import tempfile
import time
from task_context import validate, credentials, minimal_env, require
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/".github/ops"))
from tf_task_session import validated
from tf_task_worker import closed, target, ensure_membership, Stop
from tf_virtual_zip_directories import canonicalize
from tf_virtual_beta_download import archive_binding
from verified_export import export_original, model_bytes
from private_process import run as private_run
from capacity import MIN_FREE_BYTES, MAX_IPA_BYTES
import fetch_runtime

def restore_session(encoded,root):
    require(type(encoded) is str and len(encoded)<=65536 and not any(root.iterdir()),"tf_session_input")
    value=validated(json.loads(base64.b64decode(encoded,validate=True)))
    entries={"profile.json":json.dumps(value["profile"]).encode(),"tf-session.json":json.dumps(value["context"]).encode(),
        "account.plist":plistlib.dumps({"DsPrsId":value["context"]["dsid"]})}
    entries.update({"sdk/"+name:base64.b64decode(raw,validate=True) for name,raw in value["sdk_state"].items()})
    for name,raw in entries.items():
        path=root/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"wb") as stream:
            stream.write(raw)
    return value

def export_task(task,values,output,env=None,checkpoint=lambda stage:None,acceptance=None,
                load_runtime=fetch_runtime.fetch,execute=private_run):
    env=os.environ if env is None else env
    task=validate(task,env);require(task["profile"]=="tf","tf_profile_required")
    values=credentials("tf",values);model_bytes(values["FAIRPLAY_CN_MODEL_B64"])
    output=Path(output).absolute();require(not output.exists() and not output.is_symlink(),"export_destination")
    age=shutil.which("age",path=env.get("PATH"));require(age,"age_runtime_missing")
    def stage(name):
        require(int(time.time())<task["deadline"],"task_deadline");checkpoint(name)
    repo=Path(__file__).resolve().parents[3]
    pins=json.loads(Path(__file__).with_name("runtime-pins.json").read_text())
    with tempfile.TemporaryDirectory(prefix="circle-private-tf-") as folder:
        root=Path(folder);root.chmod(0o700)
        state=root/"state";package=root/"package";home=root/"home"
        for path in (state,package,home):path.mkdir(mode=0o700)
        stage("restoring_saved_session");restore_session(values["TF_SAVED_SESSION_B64"],state)
        require(shutil.disk_usage(root).free>=MIN_FREE_BYTES,"insufficient_export_disk")
        stage("loading_runtime")
        for variant in ("cn","testflight"):
            loaded=load_runtime(repo,pins,variant,root/variant)
            require(loaded.get("schema")=="circleci-native-fetch-v1" and loaded.get("source")==pins["source"] and
                loaded.get("variant")==variant and loaded.get("archive_sha256")==pins["variants"][variant]["archive_sha256"],
                "runtime_fetch_proof")
        request=dict(schema="tf-worker-request-circleci-v1",request_id=task["request_id"],invite=task["target"],
            run_id=task["run_id"],source_commit=task["source_sha"],job_id=task["job_id"],
            worker_job_id=task["worker_job_id"],deadline=task["deadline"])
        request_path=state/"request.json"
        with os.fdopen(os.open(request_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"w") as stream:
            json.dump(request,stream)
        child=minimal_env(env,home)
        child.update({key:env[key] for key in ("CIRCLECI","CIRCLE_PROJECT_USERNAME","CIRCLE_PROJECT_REPONAME",
            "CIRCLE_BRANCH","CIRCLE_SHA1","CIRCLE_WORKFLOW_JOB_ID")})
        child["RUNTIME_RUN_ID"]=task["run_id"]
        def run(binary,args,environment,timeout):
            return execute(binary,args,environment,min(timeout,task["deadline"]-int(time.time())),
                root,lambda:stage("working"))
        def native(mode,unused_state,unused_request,unused_package,unused_env):
            result=run(root/"testflight"/"tf_virtual_client",["--tf-task",mode,state,request_path,package],
                child,1200 if mode=="download" else 180)
            require(0<len(result.stdout)<=8192,"tf_native_response")
            value=closed(json.loads(result.stdout))
            if value["status"]=="session_requires_maintenance":raise Stop("testflight_session_requires_maintenance")
            if value["status"]=="rate_limited":raise Stop("testflight_rate_limited")
            return result.returncode,value
        def remote(action,args,unused_env):
            stage("checking_acceptance_permit")
            # No legacy SSH/Actions broker or historical invite re-acceptance fallback.
            require(callable(acceptance),"testflight_acceptance_handoff_required")
            return acceptance(action,args,task)
        result=dict(acceptance_attempted=False)
        stage("authenticating")
        ensure_membership(state,request_path,package,request,{},result,runner=native,remote=remote)
        bundle,identifier=target(state)
        stage("downloading");code,downloaded=native("download",state,request_path,package,{})
        require(code==0 and downloaded["downloaded"] and downloaded["membership_verified"],"testflight_download_failed")
        original=package/"beta.ipa"
        require(original.is_file() and not original.is_symlink() and 0<original.stat().st_size<=MAX_IPA_BYTES,"testflight_archive_size")
        archive_binding(original,bundle)
        normalized=root/"canonical.ipa";canonicalize(original,normalized);archive_binding(normalized,bundle)
        staged=root/"sealed-out"
        receipt=export_original(task,root/"cn"/"offline-engine",age,root,normalized,
            dict(bundleId=bundle,trackId=identifier),values["FAIRPLAY_CN_MODEL_B64"],staged,env,run,stage)
        receipt.update(acceptance_attempted=result["acceptance_attempted"])
        (staged/"receipt.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
        stage("finalizing_ciphertext");require(not output.exists() and not output.is_symlink(),"export_destination")
        staged.rename(output)
        try:stage("artifact_ready")
        except BaseException:
            shutil.rmtree(output,ignore_errors=True);raise
        return receipt
