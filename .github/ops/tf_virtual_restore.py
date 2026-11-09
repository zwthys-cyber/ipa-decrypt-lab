"""Restore the fixed authenticated state while preserving its original virtual identity."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from telegram_queue import GitHub

RUN=42694923538
ORIGIN_RUN=42650873653
ORIGIN_SOURCE="19244adbe73f71156a91a5c1cb20965925928054"
SOURCE="e86e8c8773955951492dcd1b31b1c5c75babbd34"
ARCHIVE_DIGEST="sha256:87064c512d191696bd8a4a12906e17f685fc56437196006176e7035720c14f80"
CIPHER_DIGEST="214dd5ef48c9d38dc59833f3e20f26f8fe57fed640a8122b42959bfbfee47a10"

def require(value):
    if not value:raise ValueError("tf_virtual_restore_invalid")

def unpack_private(raw,root):
    require(len(raw)<=32*1024*1024 and not any(root.iterdir()))
    files={};total=0
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as archive:
        members=archive.getmembers()
        require(0<len(members)<=128)
        for member in members:
            path=PurePosixPath(member.name)
            require(not path.is_absolute() and all(part not in ("",".","..") for part in path.parts))
            require(member.name==str(path) and member.isfile() and not member.mode&0o077)
            require(member.name not in files and 0<=member.size<=16*1024*1024)
            require(member.name in {"profile.json","account.plist","mac-store.plist","tf-session.json","catalog.json","failure.txt","store-auth-response.bin","store-auth-meta.json","tf-auth-response.bin","tf-auth-meta.json","invitation.json","accept-response.json","invitation-intents.sqlite","invitation-intent-approved.json","tf-install-metadata.json","download-failure.txt","tf-install-response.json"}
                    or len(path.parts)>=2 and path.parts[0]=="sdk"
                    and all(re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",part) is not None for part in path.parts[1:]))
            total+=member.size;require(total<=32*1024*1024)
            stream=archive.extractfile(member);require(stream is not None)
            data=stream.read(member.size+1);require(len(data)==member.size)
            files[member.name]=data
    require("profile.json" in files and "sdk/identity.json" in files)
    profile=json.loads(files["profile.json"])
    require(type(profile) is dict and profile.get("schema")=="testflight-virtual-profile-v1"
            and profile.get("origin")=="independent_sdk_virtual_identity"
            and profile.get("run_id")==str(ORIGIN_RUN) and profile.get("source_commit")==ORIGIN_SOURCE
            and type(profile.get("hardware20")) is str
            and re.fullmatch(r"[a-f0-9]{40}",profile["hardware20"]) is not None)
    for name,data in files.items():
        target=root.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        with target.open("xb") as stream:stream.write(data)
        target.chmod(0o600)

def restore(root,env):
    require(env.get("TF_VIRTUAL_RESTORE_RUN")==str(RUN) and env.get("GITHUB_ACTIONS")=="true")
    api=GitHub(env["GH_TOKEN"])
    run=api.call("/actions/runs/"+str(RUN))
    require(run.get("head_sha")==SOURCE and run.get("head_branch")=="main" and run.get("status")=="completed"
            and run.get("conclusion")=="success" and run.get("run_attempt")==1
            and run.get("path")==".github/workflows/testflight-virtual.yml")
    items=api.call("/actions/runs/"+str(RUN)+"/artifacts?per_page=100")["artifacts"]
    found=[item for item in items if item.get("name")=="tf-invite-resolution-"+str(RUN)+"-attempt-1" and not item.get("expired")]
    require(len(found)==1)
    item=found[0]
    require(item.get("digest")==ARCHIVE_DIGEST and 0<item.get("size_in_bytes",0)<4*1024*1024)
    with tempfile.TemporaryDirectory(prefix="tf-restore-",dir=env["RUNNER_TEMP"]) as folder:
        work=Path(folder);work.chmod(0o700)
        archive=work/"sealed.zip";api.archive(item["id"],archive,max_bytes=4*1024*1024)
        require("sha256:"+hashlib.sha256(archive.read_bytes()).hexdigest()==ARCHIVE_DIGEST)
        with zipfile.ZipFile(archive) as zipped:
            require(len(zipped.infolist())==2 and set(zipped.namelist())=={"tf-accept-state.age","tf-accept-receipt.json"})
            require(all(info.file_size<4*1024*1024 for info in zipped.infolist()))
            cipher=zipped.read("tf-accept-state.age")
            receipt=json.loads(zipped.read("tf-accept-receipt.json"))
        require(hashlib.sha256(cipher).hexdigest()==CIPHER_DIGEST and receipt.get("source_commit")==SOURCE
                and receipt.get("run_id")==str(RUN) and receipt.get("sealed_state_sha256")==CIPHER_DIGEST
                and receipt.get("invitation_accepted") is True and receipt.get("details_result",{}).get("status")=="invitation_binding_verified"
                and receipt.get("result",{}).get("tf_authenticated") is True
                and receipt.get("status")=="membership_verified" and receipt.get("result",{}).get("catalog_received") is True)
        identity=work/"identity.txt"
        identity.write_text(env["DELIVERY_AGE_IDENTITY"]);identity.chmod(0o600)
        child={k:env[k] for k in ("HOME","PATH","LANG") if k in env}
        result=subprocess.run(["age","-d","-i",str(identity)],input=cipher,capture_output=True,timeout=30,env=child)
        require(result.returncode==0)
        unpack_private(result.stdout,root)
        require((root/"account.plist").is_file() and (root/"tf-session.json").is_file() and (root/"invitation.json").is_file())
