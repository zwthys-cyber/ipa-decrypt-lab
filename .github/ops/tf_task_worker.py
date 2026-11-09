"""General TestFlight worker: saved session, durable acceptance permit and fully verified private export."""
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from capacity import MAX_IPA_BYTES,MIN_FREE_BYTES
from private_export import export_original,ExportError
from task_progress import WorkerProgress
from telegram_queue import GitHub
from tf_task_session import restore,RECIPIENT
from tf_task_contract import fingerprint as worker_fingerprint
from tf_task_ssh import fetch,rpc
from tf_virtual_zip_directories import canonicalize
from tf_virtual_beta_download import archive_binding
from tf_virtual import public_env

KEYS={"schema","status","http_status","membership_verified","invitation_open","agreement_required","downloaded","transport_mode",
    "archive_members","encrypted_images","clear_images","downloaded_bytes","output_bytes"}
STATUSES={"failed","session_requires_maintenance","rate_limited","membership_verified","invitation_available",
    "invitation_unavailable","acceptance_response_received","beta_downloaded"}
class Stop(Exception):pass
def need(value,status="testflight_worker_failed"):
    if not value:raise Stop(status)
def runtime(env):
    need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REF")=="refs/heads/main" and env.get("GITHUB_RUN_ATTEMPT")=="1")
    need(re.fullmatch(r"tf_[a-f0-9]{32}",env.get("DELIVERY_REQUEST_ID","")) and re.fullmatch(r"[A-Za-z0-9_-]{6,80}",env.get("DELIVERY_INVITE","")))
    need(env.get("TF_TASK_MODE") in {"inspect","export"} and re.fullmatch(r"[1-9][0-9]{0,19}",env.get("GITHUB_RUN_ID","")) and
        re.fullmatch(r"[a-f0-9]{40}",env.get("GITHUB_SHA","")))
    need(not any(env.get(key) for key in ("APPLE_ID","APPLE_PASSWORD","APPLE_CN_ID","APPLE_CN_PASSWORD","APPLE_CN_SESSION_B64","FAIRPLAY_STATE_B64","FAIRPLAY_CN_STATE_B64","FAIRPLAY_MODEL_B64")))
    return {"schema":"tf-worker-request-v1","request_id":env["DELIVERY_REQUEST_ID"],"invite":env["DELIVERY_INVITE"],
        "run_id":env["GITHUB_RUN_ID"],"source_commit":env["GITHUB_SHA"]}
def closed(value):
    need(type(value) is dict and set(value)==KEYS and value["schema"]=="tf-task-native-v1")
    need(value["status"] in STATUSES and value["transport_mode"] in {"unknown","plain_zip","encrypted"})
    need(all(type(value[key]) is bool for key in ("membership_verified","invitation_open","agreement_required","downloaded")))
    for key,limit in (("http_status",599),("archive_members",1000000),("encrypted_images",100000),("clear_images",100000),
            ("downloaded_bytes",MAX_IPA_BYTES),("output_bytes",MAX_IPA_BYTES)):
        need(type(value[key]) is int and 0<=value[key]<=limit)
    if value["downloaded"]:need(value["status"]=="beta_downloaded" and value["membership_verified"] and value["output_bytes"]>0)
    return value
def native(mode,state,request,package,env):
    child=public_env(env)
    child.update({key:env[key] for key in ("GITHUB_RUN_ID","GITHUB_SHA","GITHUB_RUN_ATTEMPT","GITHUB_REF") if key in env})
    result=subprocess.run([str(Path("tf-sdk-build/tf_virtual_client").resolve()),"--tf-task",mode,str(state),str(request),str(package)],
        capture_output=True,timeout=1200 if mode=="download" else 180,env=child)
    need(0<len(result.stdout)<=8192)
    value=closed(json.loads(result.stdout))
    if value["status"]=="session_requires_maintenance":raise Stop("testflight_session_requires_maintenance")
    if value["status"]=="rate_limited":raise Stop("testflight_rate_limited")
    return result.returncode,value
def target(state):
    info=json.loads((state/"invitation.json").read_bytes());app=info.get("app",{})
    bundle=app.get("bundleId");identifier=app.get("appAdamId")
    need(type(bundle) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{1,254}",bundle),"testflight_invitation_unavailable")
    need(type(identifier) in (str,int) and re.fullmatch("[1-9][0-9]{0,19}",str(identifier)),"testflight_invitation_unavailable")
    return bundle,str(identifier)
def ensure_membership(state,path,package,request,env,receipt,runner=native,remote=rpc):
    code,value=runner("inspect",state,path,package,env)
    need(code==0 and not value["agreement_required"],"testflight_invitation_unavailable")
    if value["membership_verified"]:return value
    need(value["status"]=="invitation_available" and value["invitation_open"],"testflight_invitation_unavailable")
    original_target=target(state)
    args={key:request[key] for key in ("invite","request_id","run_id","source_commit")}
    permit=remote("claim",args,env)
    need(permit.get("schema")=="tf-accept-permit-v1" and permit.get("permitted") is True,"testflight_acceptance_outcome_unknown")
    need(all(permit.get(key)==item for key,item in args.items()) and type(permit.get("nonce")) is str and re.fullmatch("[a-f0-9]{32}",permit["nonce"])
        and type(permit.get("expires")) is int,"testflight_acceptance_outcome_unknown")
    (state/"accept-permit.json").write_text(json.dumps(permit));(state/"accept-permit.json").chmod(0o600)
    receipt["acceptance_attempted"]=True
    verified=False
    try:
        # One POST only. Read back membership even when the POST response is ambiguous.
        try:runner("accept",state,path,package,env)
        except Stop as error:
            if str(error) in {"testflight_rate_limited","testflight_session_requires_maintenance"}:raise
        except Exception:pass
        code,value=runner("inspect",state,path,package,env)
        verified=code==0 and value["membership_verified"] and not value["agreement_required"] and target(state)==original_target
        need(verified,"testflight_acceptance_outcome_unknown")
        return value
    finally:
        try:remote("finish",dict(args,nonce=permit["nonce"],outcome="membership_verified" if verified else "outcome_unknown"),env)
        except Exception:pass

def finish_inspection(progress,env):
    # Complete only this process's own check; never call an inspection artifact-ready.
    if progress.check is None:return
    try:
        GitHub(env["GH_TOKEN"]).call("/check-runs/"+str(progress.check),
            {"status":"completed","conclusion":"neutral","output":{"title":"TestFlight inspection complete",
                "summary":"Read-only session and membership inspection; no download or file send."}},"PATCH")
    except Exception:pass

def main():
    env=dict(os.environ);os.umask(0o077)
    def stop(*args):raise InterruptedError()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    receipt={"schema":"tf-worker-result-v1","status":"testflight_worker_failed","request_id":env.get("DELIVERY_REQUEST_ID"),
        "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA"),"acceptance_attempted":False,
        "invitation_accepted":False,"downloaded":False,"decryption_proven":False,"delivered":False,"new_authorization":False}
    receipt["worker_fingerprint"]=worker_fingerprint()
    progress=WorkerProgress(env.get("DELIVERY_REQUEST_ID",""))
    try:
        request=runtime(env);mode=env["TF_TASK_MODE"]
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-task-state-") as state_dir,tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-task-private-") as package_dir:
            state=Path(state_dir);state.chmod(0o700);package=Path(package_dir);package.chmod(0o700)
            progress.advance("authenticating")
            restore(fetch(env),state,env)
            path=state/"request.json";path.write_text(json.dumps(request));path.chmod(0o600)
            if mode=="inspect":
                code,value=native("inspect",state,path,package,env);receipt["result"]=value
                need(code==0,"testflight_invitation_unavailable")
                receipt.update(status="testflight_inspection_complete",invitation_accepted=value["membership_verified"])
            else:
                need(shutil.disk_usage(package).free>=MIN_FREE_BYTES,"insufficient_export_disk")
                ensure_membership(state,path,package,request,env,receipt)
                receipt["invitation_accepted"]=True;bundle,identifier=target(state)
                progress.advance("downloading");code,value=native("download",state,path,package,env);receipt["result"]=value
                need(code==0 and value["downloaded"] and value["membership_verified"],"testflight_download_failed")
                original=package/"beta.ipa";need(original.is_file() and 0<original.stat().st_size<=MAX_IPA_BYTES)
                archive_binding(original,bundle);receipt["downloaded"]=True;progress.advance("auditing")
                normalized=package/"canonical.ipa";receipt["archive_normalization"]=canonicalize(original,normalized);archive_binding(normalized,bundle)
                need(env.get("FAIRPLAY_CN_MODEL_B64"),"testflight_model_unavailable")
                os.environ["FAIRPLAY_MODEL_B64"]=env["FAIRPLAY_CN_MODEL_B64"]
                try:
                    verified=export_original(str(Path("cn-runtime/offline-engine").resolve()),str(Path("cn-runtime/delivery-crypt").resolve()),
                        package,normalized,{"bundleId":bundle},identifier,request["request_id"],RECIPIENT,Path("delivery-out"),progress.advance,profile="tf")
                except ExportError:raise Stop("testflight_plaintext_validation_failed") from None
                finally:os.environ.pop("FAIRPLAY_MODEL_B64",None)
                receipt_path=Path("delivery-out/receipt.json");delivery=json.loads(receipt_path.read_bytes())
                delivery.update(target_type="testflight",testflight_invite=request["invite"]);receipt_path.write_text(json.dumps(delivery,sort_keys=True))
                receipt.update(status="encrypted_artifact_ready",decryption_proven=True,encrypted_images=verified["encrypted_images"],decrypted_pages=verified["decrypted_pages"])
                progress.advance("artifact_ready")
    except Stop as error:receipt["status"]=str(error)
    except Exception:pass
    success=receipt["status"] in {"testflight_inspection_complete","encrypted_artifact_ready"}
    if success and env.get("TF_TASK_MODE")=="inspect":finish_inspection(progress,env)
    if not success:
        shutil.rmtree("delivery-out",ignore_errors=True);progress.advance("failed")
    Path("tf-worker-result.json").write_text(json.dumps(receipt,sort_keys=True))
    output=env.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a") as stream:stream.write("status="+receipt["status"]+"\n")
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if success else 2
if __name__=="__main__":raise SystemExit(main())
