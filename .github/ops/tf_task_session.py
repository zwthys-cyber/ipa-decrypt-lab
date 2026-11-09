"""Minimal saved TestFlight context, decrypted on GitHub only; no GSA/Store password state."""
import json
import base64
import os
from pathlib import Path
import plistlib
import re
import subprocess

ORIGIN_RUN="42650873653"
ORIGIN_SOURCE="19244adbe73f71156a91a5c1cb20965925928054"
RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"
def need(value):
    if not value:raise ValueError("tf_session_invalid")
def validated(value):
    need(type(value) is dict and set(value)=={"schema","profile","context","sdk_state"} and value["schema"]=="tf-saved-session-v1")
    profile,context=value["profile"],value["context"]
    need(type(profile) is dict and profile.get("schema")=="testflight-virtual-profile-v1" and
        profile.get("origin")=="independent_sdk_virtual_identity" and profile.get("run_id")==ORIGIN_RUN
        and profile.get("source_commit")==ORIGIN_SOURCE)
    need(type(profile.get("hardware20")) is str and re.fullmatch("[a-f0-9]{40}",profile["hardware20"]))
    need(type(context) is dict and set(context)=={"accountId","sessionId","dsid","udid","deviceVendorId","deviceName","deviceModel","headers"})
    need(context["udid"]==profile["hardware20"] and type(context["dsid"]) is str and re.fullmatch("[1-9][0-9]{0,19}",context["dsid"]))
    for key,limit in (("accountId",256),("sessionId",4096),("deviceVendorId",128),("deviceName",256),("deviceModel",128)):
        need(type(context[key]) is str and 0<len(context[key])<=limit and all(ord(c)>=32 and ord(c)!=127 for c in context[key]))
    need(re.fullmatch(r"(?:Mac|MacBook|Macmini|MacPro|iMac)[A-Za-z0-9,.-]{1,100}",context["deviceModel"]))
    need(type(context["headers"]) is dict and set(context["headers"])=={"X-Apple-AMD-M","X-Apple-Store-Front"})
    need(all(type(item) is str and 0<len(item)<8192 and "\n" not in item and "\r" not in item for item in context["headers"].values()))
    sdk=value["sdk_state"]
    need(type(sdk) is dict and 0<len(sdk)<=64 and "identity.json" in sdk)
    total=0
    for name,encoded in sdk.items():
        need(type(name) is str and name==str(Path(name)) and not Path(name).is_absolute()
            and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",part) and part not in {".",".."} for part in Path(name).parts))
        raw=base64.b64decode(encoded,validate=True);total+=len(raw)
        need(total<=128*1024)
    need(len(json.dumps(value).encode())<=256*1024)
    return value
def snapshot(root):
    sdk={}
    for path in (root/"sdk").rglob("*"):
        need(not path.is_symlink())
        if path.is_file():
            need(path.stat().st_mode&0o077==0)
            sdk[path.relative_to(root/"sdk").as_posix()]=base64.b64encode(path.read_bytes()).decode()
    return validated({"schema":"tf-saved-session-v1","profile":json.loads((root/"profile.json").read_bytes()),
        "context":json.loads((root/"tf-session.json").read_bytes()),"sdk_state":sdk})
def child_env(env):
    return {key:env[key] for key in ("HOME","PATH","LANG") if key in env}
def encrypt(value,env):
    need(env.get("GITHUB_ACTIONS")=="true");value=validated(value)
    result=subprocess.run(["age","-r",RECIPIENT],input=json.dumps(value,separators=(",",":")).encode(),
        capture_output=True,timeout=30,env=child_env(env))
    need(result.returncode==0 and result.stdout.startswith(b"age-encryption.org/v1\n") and len(result.stdout)<=256*1024)
    return result.stdout
def restore(cipher,root,env):
    need(env.get("GITHUB_ACTIONS")=="true" and 0<len(cipher)<=256*1024 and not any(root.iterdir()))
    identity=root/"key.txt";identity.write_text(env["DELIVERY_AGE_IDENTITY"]);identity.chmod(0o600)
    try:
        result=subprocess.run(["age","-d","-i",str(identity)],input=cipher,capture_output=True,timeout=30,env=child_env(env))
        need(result.returncode==0 and len(result.stdout)<=256*1024)
        value=validated(json.loads(result.stdout))
    finally:identity.unlink(missing_ok=True)
    for name,raw in (("profile.json",json.dumps(value["profile"]).encode()),("tf-session.json",json.dumps(value["context"]).encode()),
            ("account.plist",plistlib.dumps({"DsPrsId":value["context"]["dsid"]}))):
        path=root/name;path.write_bytes(raw);path.chmod(0o600)
    for name,encoded in value["sdk_state"].items():
        path=root/"sdk"/name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        path.write_bytes(base64.b64decode(encoded,validate=True));path.chmod(0o600)
    return value
