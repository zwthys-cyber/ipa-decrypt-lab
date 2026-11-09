"""One bounded isolated virtual-profile experiment; only sealed state leaves CI."""
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile
import tempfile

KEYS={"schema","stage","status","virtual_identity","account_login_attempted","gsa_authenticated",
      "mac_store_authenticated","tf_authenticated","catalog_received","verification_requested",
      "http_status","sdk_error_code"}
STAGES={"initialization","grandslam_provisioning","grandslam_login","mac_store_login",
        "testflight_session","testflight_catalog"}
def validate(value):
    if type(value) is not dict or set(value)!=KEYS:raise ValueError()
    if value["schema"]!="testflight-virtual-auth-v1" or value["stage"] not in STAGES:
        raise ValueError()
    if value["status"] not in {"failed","verification_required","catalog_verified"}:raise ValueError()
    for key in ("virtual_identity","account_login_attempted","gsa_authenticated","mac_store_authenticated",
                "tf_authenticated","catalog_received","verification_requested"):
        if type(value[key]) is not bool:raise ValueError()
    if value["virtual_identity"] is not True:raise ValueError()
    for key,bound in (("http_status",599),("sdk_error_code",7)):
        if type(value[key]) is not int or not 0<=value[key]<=bound:raise ValueError()
    flags=[value[key] for key in ("account_login_attempted","gsa_authenticated","mac_store_authenticated",
                                  "tf_authenticated","catalog_received")]
    if any(flags[i] and not flags[i-1] for i in range(1,len(flags))):raise ValueError()
    if value["status"]=="catalog_verified" and not all(flags):raise ValueError()
    if value["status"]=="verification_required" and not value["verification_requested"]:raise ValueError()
    return value

def public_env(env):
    result={k:env[k] for k in ("HOME","PATH","LANG","RUNNER_TEMP") if k in env}
    result["GITHUB_ACTIONS"]="true"
    return result

def pack_private(root):
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode="w:gz") as archive:
        total=0
        for path in sorted(root.rglob("*")):
            if path.is_symlink():raise ValueError()
            if path.is_dir():continue
            if not path.is_file() or path.stat().st_mode&0o077:raise ValueError()
            total+=path.stat().st_size
            if total>32*1024*1024:raise ValueError()
            archive.add(path,arcname=path.relative_to(root),recursive=False)
    return output.getvalue()

def main():
    os.umask(0o077)
    receipt={"schema":"testflight-virtual-experiment-v1","status":"experiment_failed",
             "virtual_identity":True,"invitation_accepted":False,"downloaded":False,
             "decryption_proven":False,"existing_credentials_changed":False}
    env=dict(os.environ);child=public_env(env)
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        email=env.get("APPLE_CN_ID","");password=env.get("APPLE_CN_PASSWORD","")
        if not email or not password or any(c in email+password for c in "\r\n"):raise ValueError()
        recipient=json.loads(Path("config/delivery.json").read_text())["recipient"]
        if recipient!="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d":raise ValueError()
        binary=str(Path("tf-sdk-build/tf_virtual_client").resolve())
        with tempfile.TemporaryDirectory(prefix="tf-virtual-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700)
            profile={"schema":"testflight-virtual-profile-v1",
                     "origin":"independent_sdk_virtual_identity","hardware20":secrets.token_hex(20),
                     "run_id":env["GITHUB_RUN_ID"],"source_commit":env["GITHUB_SHA"]}
            (root/"profile.json").write_text(json.dumps(profile))
            try:
                result=subprocess.run([binary,"--authenticate",str(root)],input=(email+"\n"+password+"\n").encode(),
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240,env=child)
                if len(result.stdout)>4096:raise ValueError()
                value=validate(json.loads(result.stdout))
                receipt["result"]=value
                receipt["status"]=value["status"]
            except subprocess.TimeoutExpired:
                receipt["status"]="experiment_timeout"
            except Exception:
                receipt["status"]="experiment_failed"
            # Retain identity/provisioning/session state only as age ciphertext, including on rejection.
            snapshot=pack_private(root)
            sealed=subprocess.run(["age","-r",recipient],input=snapshot,capture_output=True,timeout=30,env=child)
            if sealed.returncode or not sealed.stdout.startswith(b"age-encryption.org/v1\n"):raise ValueError()
            Path("tf-virtual-state.age").write_bytes(sealed.stdout)
            receipt["sealed_state_sha256"]=hashlib.sha256(sealed.stdout).hexdigest()
            receipt["sealed_state_bytes"]=len(sealed.stdout)
    except Exception:
        receipt["status"]="experiment_failed"
    receipt.update(run_id=env.get("GITHUB_RUN_ID"),source_commit=env.get("GITHUB_SHA"))
    Path("tf-virtual-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="catalog_verified" else 2
if __name__=="__main__":raise SystemExit(main())
