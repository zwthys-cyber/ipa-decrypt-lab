"""Private fixed-path FairPlay checkpoint for reuse on disposable GitHub runners."""
import argparse
import base64
import json
import os
from pathlib import Path
import plistlib
import stat
import subprocess
import sys

LIMIT=32768
FILE_LIMIT=16384
SCHEMA="ipa-lab-private-fairplay-state-v1"
FILES={
    "fpsd_sidb":"/private/var/db/fpsd/SC Info/SC Info.sidb",
    "fpsd_sids":"/private/var/db/fpsd/SC Info/SC Info.sids",
    "shared_sidb":"/Users/Shared/SC Info/SC Info.sidb",
    "shared_sids":"/Users/Shared/SC Info/SC Info.sids",
}


def decode_bytes(value,limit):
    if type(value) is not str or len(value)>4*((limit+2)//3):
        raise ValueError("invalid encoding")
    result=base64.b64decode(value,validate=True)
    if not 0<len(result)<=limit:
        raise ValueError("invalid size")
    return result


def validate(raw):
    if not 0<len(raw)<=LIMIT:
        raise ValueError("invalid checkpoint size")
    value=json.loads(raw)
    if type(value) is not dict or set(value)!={"schema","files","hardware"} or value["schema"]!=SCHEMA:
        raise ValueError("invalid checkpoint")
    hardware=decode_bytes(value["hardware"],6)
    if len(hardware)!=6:
        raise ValueError("invalid hardware")
    files=value["files"]
    if type(files) is not dict or not set(files)<=set(FILES) or "fpsd_sidb" not in files:
        raise ValueError("invalid state paths")
    decoded={key:decode_bytes(data,FILE_LIMIT) for key,data in files.items()}
    return hardware,decoded


def hardware_from_ioreg(raw):
    if len(raw)>16*1024**2:
        raise ValueError("registry oversized")
    document=plistlib.loads(raw)
    roots=document if type(document) is list else [document]
    visited=0
    def visit(node,parent,depth=0):
        nonlocal visited
        visited+=1
        if visited>100000 or depth>100:
            raise ValueError("registry traversal limit")
        if type(node) is not dict:
            return None
        if node.get("BSD Name")=="en0" and node.get("IOBuiltin") is True:
            value=parent.get("IOMACAddress") if type(parent) is dict else None
            if type(value) is bytes and len(value)==6:
                return value
        children=node.get("IORegistryEntryChildren",[])
        if type(children) is not list:
            return None
        for child in children:
            result=visit(child,node,depth+1)
            if result is not None:
                return result
        return None
    for node in roots:
        result=visit(node,None)
        if result is not None:
            return result
    raise ValueError("hardware unavailable")


def read_state_file(path):
    try:
        info=path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=FILE_LIMIT:
        raise ValueError("invalid state file")
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(descriptor,"rb") as source:
        actual=os.fstat(source.fileno())
        if actual.st_ino!=info.st_ino or actual.st_dev!=info.st_dev:
            raise ValueError("state file changed")
        data=source.read(FILE_LIMIT+1)
    if not 0<len(data)<=FILE_LIMIT:
        raise ValueError("invalid state file size")
    return data


def capture():
    result=subprocess.run(["/usr/sbin/ioreg","-a","-l","-r","-k","IOMACAddress","-p","IOService"],
                          env={"PATH":"/usr/bin:/bin"},stdin=subprocess.DEVNULL,
                          capture_output=True,timeout=10)
    if result.returncode:
        raise ValueError("registry unavailable")
    hardware=hardware_from_ioreg(result.stdout)
    files={}
    for key,name in FILES.items():
        data=read_state_file(Path(name))
        if data is not None:
            files[key]=base64.b64encode(data).decode("ascii")
    raw=json.dumps({"schema":SCHEMA,"files":files,
                    "hardware":base64.b64encode(hardware).decode("ascii")},
                   sort_keys=True,separators=(",",":")).encode()
    validate(raw)
    return raw


def write_private(path,data):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,"wb") as target:
        target.write(data)


def materialize(encoded,root):
    raw=decode_bytes(encoded,LIMIT)
    hardware,files=validate(raw)
    root.mkdir(mode=0o700)
    for name in ("fpsd","shared","adi"):
        (root/name).mkdir(mode=0o700)
    hardware_path=root/"iomac.bin"
    write_private(hardware_path,hardware)
    for key,data in files.items():
        directory,kind=key.split("_")
        write_private(root/directory/("SC Info."+kind),data)
    return {"hardware":hardware_path,"fpsd":root/"fpsd","shared":root/"shared","adi":root/"adi"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--uid",type=int,required=True)
    parser.add_argument("--gid",type=int,required=True)
    args=parser.parse_args()
    report={"schema":"ipa-lab-private-state-checkpoint-v1","status":"checkpoint_failed",
            "plaintext_published":False,"authorization_request_attempted":False}
    try:
        if os.environ.get("GITHUB_ACTIONS")!="true" or sys.platform!="darwin" or os.geteuid()!=0:
            raise ValueError("host rejected")
        target=Path(args.output)
        parent=target.parent.resolve(strict=True)
        info=parent.stat()
        if (not target.is_absolute() or target.name!="state.json"
                or not parent.name.startswith("ipa-lab-model-bootstrap-")
                or args.uid<=0 or args.gid<0 or info.st_uid!=args.uid
                or info.st_mode&0o077 or target.exists() or target.is_symlink()):
            raise ValueError("destination rejected")
        raw=capture()
        write_private(parent/target.name,raw)
        os.chown(parent/target.name,args.uid,args.gid)
        report["status"]="checkpoint_captured"
    except Exception:
        pass
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="checkpoint_captured" else 2


if __name__=="__main__":
    raise SystemExit(main())
