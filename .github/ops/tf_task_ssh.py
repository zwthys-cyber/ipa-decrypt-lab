"""Pinned SSH RPC for ciphertext storage and noncredential acceptance intents."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from contextlib import contextmanager

@contextmanager
def connection(env):
    host=env.get("VPS_HOST","")
    if not re.fullmatch("[A-Za-z0-9.-]{1,253}",host):raise ValueError("tf_state_transport_invalid")
    with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-state-ssh-") as folder:
        root=Path(folder);root.chmod(0o700);known=root/"known_hosts";known.write_text(env["VPS_KNOWN_HOSTS"]);known.chmod(0o600)
        options=["-o","UserKnownHostsFile="+str(known),"-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=15"]
        child={key:env[key] for key in ("PATH","HOME","LANG","SSHPASS") if key in env}
        yield host,options,child,root
def rpc(operation,value,env):
    if operation not in {"status","install","claim","finish"}:raise ValueError()
    with connection(env) as (host,options,child,root):
        result=subprocess.run(["sshpass","-e","ssh"]+options+["root@"+host,
            "env LAB_RUNTIME=vps PYTHONDONTWRITEBYTECODE=1 python3 /opt/ipazake/testflight-state.py "+operation],
            input=json.dumps(value).encode(),capture_output=True,timeout=45,env=child)
        if result.returncode or not 0<len(result.stdout)<=16384:raise ValueError("tf_state_transport_failed")
        parsed=json.loads(result.stdout)
        if type(parsed) is not dict or parsed.get("status")=="failed":raise ValueError("tf_state_operation_failed")
        return parsed
def fetch(env):
    status=rpc("status",{},env)
    if status.get("schema")!="tf-state-status-v1" or status.get("ready") is not True or status.get("origin_run")!="42650873653":raise ValueError("tf_session_not_ready")
    if type(status.get("sha256")) is not str or not re.fullmatch("[a-f0-9]{64}",status["sha256"]):raise ValueError()
    if type(status.get("bytes")) is not int or not 0<status["bytes"]<=256*1024:raise ValueError()
    with connection(env) as (host,options,child,root):
        target=root/"state.age"
        result=subprocess.run(["sshpass","-e","scp","-q"]+options+["root@"+host+":/var/lib/ipazake/testflight/session.age",str(target)],
            capture_output=True,timeout=45,env=child)
        if result.returncode:raise ValueError("tf_state_transport_failed")
        cipher=target.read_bytes()
        if len(cipher)!=status["bytes"] or hashlib.sha256(cipher).hexdigest()!=status["sha256"]:raise ValueError()
        return cipher
