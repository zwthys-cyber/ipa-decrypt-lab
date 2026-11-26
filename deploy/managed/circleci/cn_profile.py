"""CircleCI CN saved-session adapter. No password login, profile bootstrap or GitHub flags."""
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time
from task_context import credentials, minimal_env, require
from store_account_summary import validate_session
import private_fairplay_state as checkpoint
UA="Configurator/2.21 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6"

def decode(values,now=None):
    values=credentials("cn",values)
    now=int(time.time()) if now is None else now
    raw=checkpoint.decode_bytes(values["APPLE_CN_SESSION_B64"],32768)
    value=json.loads(raw)
    require(type(value) is dict and set(value)=={"schema","email","guid","store","created","account"},"cn_session_schema")
    email=values["APPLE_CN_ID"].strip();guid=values["APPLE_CN_GUID"].upper()
    require(email and re.fullmatch(r"[A-F0-9]{12}",guid) and value["schema"]=="cn-account-session-v1" and
        value["store"]=="143465" and type(value["email"]) is str and value["email"].casefold()==email.casefold() and
        value["guid"]==guid and type(value["created"]) is int and 0<value["created"]<=now+60,"cn_session_binding")
    account=value["account"]
    require(type(account) is dict and type(account.get("email")) is str and
        account["email"].casefold()==email.casefold() and account.get("store")=="143465","cn_account_binding")
    front=account.get("labStoreFront") or "143465-1"
    require(type(front) is str and front.startswith("143465-"),"cn_storefront")
    validate_session(dict(dsid=account.get("directoryServicesIdentifier"),guid=guid,
        token=account.get("passwordToken"),user_agent=UA,storefront=front,cookies=account.get("cookie")))
    hardware,_=checkpoint.validate(checkpoint.decode_bytes(values["FAIRPLAY_CN_STATE_B64"],checkpoint.LIMIT))
    require(hardware.hex().upper()==guid,"cn_checkpoint_guid")
    model=checkpoint.decode_bytes(values["FAIRPLAY_CN_MODEL_B64"],8192)
    require(len(model)==4184 and model[:8]==b"FPSENR2\x00" and
        struct.unpack_from("<II",model,8)==(2,len(model)),"cn_model_format")
    return value

def bound(path,value,values):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=32768,"cn_account_cache")
    current=dict(value,account=json.loads(path.read_bytes()))
    decode(dict(values,APPLE_CN_SESSION_B64=base64.b64encode(json.dumps(current).encode()).decode()))
    return current

@contextmanager
def saved_session(binary,helper,values,env,home,runner):
    value=decode(values)
    folder=home/".ipatool"/hashlib.md5(value["email"].lower().encode()).hexdigest()
    folder.mkdir(mode=0o700,parents=True,exist_ok=False)
    path=folder/"account.json"
    child=minimal_env(env,home);child["LAB_KBSYNC_HELPER"]=str(helper)
    try:
        with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"w") as stream:
            json.dump(value["account"],stream)
        result=runner(binary,["resume-cn",value["email"],"--guid",value["guid"]],child,300)
        require(result.returncode==0,"cn_session_requires_maintenance")
        bound(path,value,values)
        yield value,child,path
        bound(path,value,values)
    finally:
        import shutil
        shutil.rmtree(home/".ipatool",ignore_errors=True)
