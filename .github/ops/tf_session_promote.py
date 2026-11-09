"""Promote the proven TF context as private durable ciphertext, without new authentication."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from tf_task_session import snapshot,encrypt
from tf_task_ssh import connection,rpc
from tf_virtual_restore import restore

def install_helper(env):
    source=env["GITHUB_SHA"]
    if not re.fullmatch("[a-f0-9]{40}",source):raise ValueError()
    helper=Path("tools/testflight_state.py");digest=hashlib.sha256(helper.read_bytes()).hexdigest()
    with connection(env) as (host,options,child,root):
        destination="/root/tf-state-"+source+".py"
        copied=subprocess.run(["sshpass","-e","scp","-q"]+options+[str(helper),"root@"+host+":"+destination],capture_output=True,timeout=45,env=child)
        if copied.returncode:raise ValueError()
        command="""set -eu
source=$1
digest=$2
staged=/root/tf-state-$source.py
trap 'rm -f "$staged"' EXIT
test "$(sha256sum "$staged" | cut -d ' ' -f1)" = "$digest"
install -m 0444 "$staged" /opt/ipazake/testflight-state.py
"""
        installed=subprocess.run(["sshpass","-e","ssh"]+options+["root@"+host,"bash -s -- "+source+" "+digest],
            input=command.encode(),capture_output=True,timeout=45,env=child)
        if installed.returncode:raise ValueError()
def main():
    env=dict(os.environ);os.umask(0o077)
    receipt={"schema":"tf-session-promotion-v1","status":"promotion_failed","apple_requests":0,"new_identity":False,"state_plaintext_on_vps":False}
    try:
        if env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_RUN_ATTEMPT")!="1":raise ValueError()
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-promote-private-") as folder:
            root=Path(folder);root.chmod(0o700);restore(root,env)
            cipher=encrypt(snapshot(root),env)
            install_helper(env)
            result=rpc("install",{"schema":"tf-durable-state-v1","origin_run":"42650873653",
                "ciphertext_b64":base64.b64encode(cipher).decode(),"sha256":hashlib.sha256(cipher).hexdigest()},env)
            if result.get("ready") is not True or result.get("sha256")!=hashlib.sha256(cipher).hexdigest():raise ValueError()
            receipt.update(status="ciphertext_persisted",cipher_bytes=len(cipher),cipher_sha256=result["sha256"])
    except Exception:pass
    Path("tf-session-promotion-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="ciphertext_persisted" else 2
if __name__=="__main__":raise SystemExit(main())
