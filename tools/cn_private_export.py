"""Verified CN latest export using only the stored independent CN profile."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
from account_profile import profile_for_request
from cn_account import decode
import private_fairplay_state as checkpoint
from app_preflight import check_app,PreflightError
from private_export import (require,ExportError,export_original,main,run,check_capacity,
                            DOWNLOAD_TIMEOUT,MAX_BYTES)
from progress_stream import run_download

def validate_profile(env):
    require(not any(env.get(k) for k in ("APPLE_ID","APPLE_PASSWORD","APPLE_2FA_CODE",
                "FAIRPLAY_MODEL_B64","FAIRPLAY_STATE_B64")),"foreign_account_secrets_present")
    value,_=decode(env)
    hardware,_=checkpoint.validate(checkpoint.decode_bytes(env.get("FAIRPLAY_CN_STATE_B64",""),checkpoint.LIMIT))
    require(hardware.hex().upper()==value["guid"],"cn_saved_checkpoint_guid_mismatch")
    model=checkpoint.decode_bytes(env.get("FAIRPLAY_CN_MODEL_B64",""),8192)
    require(len(model)==4184 and model[:8]==b"FPSENR2\x00"
            and struct.unpack_from("<II",model,8)==(2,len(model)),"cn_saved_model_format_invalid")
    return value

def bound_account(path,value,env):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=32768,"cn_account_cache_invalid")
    current=dict(value,account=json.loads(path.read_bytes()))
    import base64
    decode(dict(env,APPLE_CN_SESSION_B64=base64.b64encode(json.dumps(current).encode()).decode()))
    return current

def export(binary,engine,crypt,target,request_id,recipient,output_dir,progress=None,measurement=None):
    progress=progress or (lambda stage:None)
    require(os.environ.get("GITHUB_ACTIONS")=="true","requires_github_actions")
    require(profile_for_request(request_id)=="cn","invalid_cn_request_id")
    require(not os.environ.get("DELIVERY_VERSION"),"cn_history_not_supported")
    require(re.fullmatch(r"[1-9][0-9]{4,19}",target or ""),"canonical_app_id_required")
    require(re.fullmatch(r"age1[0-9a-z]{58}",recipient or ""),"missing_delivery_recipient")
    require(not output_dir.exists(),"output_directory_exists")
    progress("metadata")
    try:info=check_app(target,profile="cn")
    except PreflightError as error:raise ExportError(error.status) from None
    check_capacity(info,output_dir.parent)
    env=dict(os.environ);value=validate_profile(env)
    folder=Path(env["HOME"])/".ipatool"/hashlib.md5(value["email"].lower().encode()).hexdigest()
    path=folder/"account.json"
    require(not folder.parent.is_symlink() and not folder.exists() and not folder.is_symlink(),"cn_cache_not_empty")
    folder.parent.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700)
    child={k:env[k] for k in ("HOME","PATH","LANG","LAB_KBSYNC_HELPER") if k in env}
    try:
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"w") as stream:
            json.dump(value["account"],stream)
        progress("authenticating")
        # No password, OTP, enrollment, alternate account or interactive code wait.
        result=run(binary,["resume-cn",value["email"],"--guid",value["guid"]],child)
        require(result.returncode==0,"cn_session_requires_maintenance")
        bound_account(path,value,env)
        with tempfile.TemporaryDirectory(prefix="ipa-cn-delivery-private-") as directory:
            root=Path(directory);root.chmod(0o700);original=root/"source.ipa"
            progress("downloading")
            args=["download",value["email"],info["bundleId"],"--guid",value["guid"],"--output",str(original)]
            result=(run_download(binary,args,child,DOWNLOAD_TIMEOUT,measurement) if measurement
                    else run(binary,args,child,timeout=DOWNLOAD_TIMEOUT))
            require(result.returncode==0 and original.is_file(),"cn_download_rejected")
            bound_account(path,value,env)
            # The common verifier sees only the CN model during this isolated worker.
            os.environ["FAIRPLAY_MODEL_B64"]=env["FAIRPLAY_CN_MODEL_B64"]
            try:
                return export_original(engine,crypt,root,original,info,target,request_id,recipient,
                                       output_dir,progress,profile="cn")
            finally:os.environ.pop("FAIRPLAY_MODEL_B64",None)
    finally:
        if folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

if __name__=="__main__":raise SystemExit(main(export))
