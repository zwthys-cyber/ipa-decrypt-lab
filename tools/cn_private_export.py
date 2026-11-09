"""Verified CN latest/historical export using only the stored independent CN profile."""
from contextlib import contextmanager
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
from version_request import selector,resolved_marker

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

@contextmanager
def saved_session(binary,env,progress=None,value=None):
    """Restore only the existing CN identity; no password, OTP or model required."""
    require(not any(env.get(k) for k in ("APPLE_ID","APPLE_PASSWORD","APPLE_2FA_CODE",
            "FAIRPLAY_MODEL_B64","FAIRPLAY_STATE_B64")),"foreign_account_secrets_present")
    if value is None:value,_=decode(env)
    folder=Path(env["HOME"])/".ipatool"/hashlib.md5(value["email"].lower().encode()).hexdigest()
    path=folder/"account.json"
    require(not folder.parent.is_symlink() and not folder.exists() and not folder.is_symlink(),"cn_cache_not_empty")
    folder.parent.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700)
    child={k:env[k] for k in ("HOME","PATH","LANG","LAB_KBSYNC_HELPER") if k in env}
    try:
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),"w") as stream:
            json.dump(value["account"],stream)
        if progress:progress("authenticating")
        result=run(binary,["resume-cn",value["email"],"--guid",value["guid"]],child)
        require(result.returncode==0,"cn_session_requires_maintenance")
        bound_account(path,value,env)
        yield value,child,path
        bound_account(path,value,env)
    finally:
        if folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

def export(binary,engine,crypt,target,request_id,recipient,output_dir,progress=None,measurement=None):
    progress=progress or (lambda stage:None)
    require(os.environ.get("GITHUB_ACTIONS")=="true","requires_github_actions")
    require(profile_for_request(request_id)=="cn","invalid_cn_request_id")
    requested=selector(os.environ.get("DELIVERY_VERSION",""))
    require(re.fullmatch(r"[1-9][0-9]{4,19}",target or ""),"canonical_app_id_required")
    require(re.fullmatch(r"age1[0-9a-z]{58}",recipient or ""),"missing_delivery_recipient")
    require(not output_dir.exists(),"output_directory_exists")
    progress("metadata")
    try:info=check_app(target,historical=bool(requested),profile="cn")
    except PreflightError as error:raise ExportError(error.status) from None
    check_capacity({} if requested else info,output_dir.parent)
    env=dict(os.environ);value=validate_profile(env)
    with saved_session(binary,env,progress,value) as (value,child,path):
        if requested:child["LAB_REQUESTED_VERSION"]=requested
        with tempfile.TemporaryDirectory(prefix="ipa-cn-delivery-private-") as directory:
            root=Path(directory);root.chmod(0o700);original=root/"source.ipa"
            progress("resolving_version" if requested else "downloading")
            args=["download",value["email"],info["bundleId"],"--guid",value["guid"],"--output",str(original)]
            result=(run_download(binary,args,child,DOWNLOAD_TIMEOUT,measurement) if measurement
                    else run(binary,args,child,timeout=DOWNLOAD_TIMEOUT))
            if requested and result.returncode!=0:
                markers=re.findall(r"^IPA_LAB_VERSION_ERROR:([a-z_]+)$",result.stdout or "",re.M)
                known={"invalid_version","version_not_found","version_search_limit","version_lookup_unavailable"}
                raise ExportError(markers[-1] if markers and markers[-1] in known else "version_download_rejected")
            require(result.returncode==0 and original.is_file(),"cn_download_rejected")
            version_id,resolved=resolved_marker(result.stdout or "",requested) if requested else ("","")
            bound_account(path,value,env)
            # The common verifier receives only the bound CN model, never the foreign model.
            os.environ["FAIRPLAY_MODEL_B64"]=env["FAIRPLAY_CN_MODEL_B64"]
            try:
                return export_original(engine,crypt,root,original,info,target,request_id,recipient,
                                       output_dir,progress,requested,version_id,resolved,profile="cn")
            finally:os.environ.pop("FAIRPLAY_MODEL_B64",None)

if __name__=="__main__":raise SystemExit(main(export))
