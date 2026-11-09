"""Transfer only the CI-tested one-shot sender over existing pinned SSH."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

STATUSES={"return_failed","already_delivered","prior_send_outcome_unknown","send_outcome_unknown","telegram_file_delivered"}
def parse(raw):
    lines=raw.decode().splitlines()
    if not lines:raise ValueError()
    value=json.loads(lines[-1])
    if type(value) is not dict or set(value)-{"schema","input_run","status","delivered","bytes"}:raise ValueError()
    if value.get("schema")!="tf-private-return-v1" or value.get("input_run")!="42701117321" or value.get("status") not in STATUSES:raise ValueError()
    if type(value.get("delivered")) is not bool:raise ValueError()
    if "bytes" in value and (type(value["bytes"]) is not int or not 0<value["bytes"]<8*1024*1024):raise ValueError()
    if value["delivered"] and value["status"] not in {"already_delivered","telegram_file_delivered"}:raise ValueError()
    return value

REMOTE="""set -eu
source_commit=$1
source_digest=$2
staged=/root/tf-private-return-$source_commit.py
final=/opt/ipazake/one-shot/tf-private-return-$source_commit.py
trap 'rm -f "$staged" "$final"' EXIT
test "$(sha256sum "$staged" | cut -d ' ' -f1)" = "$source_digest"
install -d -m 0755 /opt/ipazake/one-shot
install -m 0444 "$staged" "$final"
systemd-run --quiet --wait --pipe --collect --unit=ipazake-tf-return-42701117321 -p User=ipazake -p Group=ipazake -p LoadCredential=bot.json:/etc/ipazake/bot.json -p WorkingDirectory=/opt/ipazake/current -p UMask=0077 -p RuntimeMaxSec=600 --setenv=LAB_RUNTIME=vps --setenv=PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 "$final"
"""
def main():
    result={"schema":"tf-private-return-v1","input_run":"42701117321","status":"remote_outcome_unknown","delivered":False}
    try:
        env=dict(os.environ)
        if env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REF")!="refs/heads/main" or env.get("GITHUB_RUN_ATTEMPT")!="1":raise ValueError()
        source=env["GITHUB_SHA"];host=env["VPS_HOST"]
        if not re.fullmatch("[a-f0-9]{40}",source) or not re.fullmatch("[A-Za-z0-9.-]{1,253}",host):raise ValueError()
        sender=Path(".github/ops/tf_return_sender.py");digest=hashlib.sha256(sender.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-return-ssh-") as folder:
            root=Path(folder);root.chmod(0o700);known=root/"known_hosts";known.write_text(env["VPS_KNOWN_HOSTS"]);known.chmod(0o600)
            options=["-o","UserKnownHostsFile="+str(known),"-o","StrictHostKeyChecking=yes","-o","ConnectTimeout=15"]
            child={key:env[key] for key in ("PATH","HOME","LANG","SSHPASS") if key in env}
            copied=subprocess.run(["sshpass","-e","scp","-q"]+options+[str(sender),"root@"+host+":/root/tf-private-return-"+source+".py"],
                capture_output=True,timeout=45,env=child)
            if copied.returncode:raise ValueError()
            remote=subprocess.run(["sshpass","-e","ssh"]+options+["root@"+host,"bash -s -- "+source+" "+digest],
                input=REMOTE.encode(),capture_output=True,timeout=650,env=child)
            if len(remote.stdout)>65536:raise ValueError()
            value=parse(remote.stdout)
            if remote.returncode and value["delivered"]:raise ValueError()
            result=value
    except Exception:pass
    Path("tf-return-receipt.json").write_text(json.dumps(result,sort_keys=True))
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result["delivered"] else 2
if __name__=="__main__":raise SystemExit(main())
