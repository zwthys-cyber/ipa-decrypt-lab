"""Public-only TF native runtime, pinned to source, macOS/architecture and runtime library ABI."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from telegram_queue import GitHub

WORKFLOW=".github/workflows/testflight-runtime-build.yml"
MAX=64*1024*1024
def need(value):
    if not value:raise ValueError("tf_runtime_invalid")
def allowed(name):
    return name=="tf_virtual_client" or re.fullmatch(r"libapple_auth(?:_client)?(?:\.[0-9.]+)?\.dylib",name) is not None
def sha(path):
    with path.open("rb") as stream:return hashlib.file_digest(stream,"sha256").hexdigest()
def fingerprint(root=Path(".")):
    root=Path(root)
    paths={root/WORKFLOW,root/".github/ops/tf_task_runtime.py",root/".github/ops/tf_task_native.cpp"}
    for pattern in ("tf_sdk*","tf_virtual*.cpp","tf_virtual*.cmake","tf_virtual*patch.py"):
        paths.update(path for path in (root/".github/ops").glob(pattern) if path.is_file())
    digest=hashlib.sha256()
    for path in sorted(paths):
        need(not path.is_symlink());digest.update(path.relative_to(root).as_posix().encode()+b"\0");digest.update(bytes.fromhex(sha(path)))
    return digest.hexdigest()
def abi():
    raw=subprocess.check_output(["xcodebuild","-version"])+subprocess.check_output(["brew","list","--versions","mbedtls@3","curl","libzip"])
    return hashlib.sha256(raw).hexdigest()
def unpack(path,destination,stamp,abi_hash,source,run):
    need(not destination.exists());destination.mkdir(mode=0o700)
    with tarfile.open(path,"r:gz") as archive:
        members=archive.getmembers();need(1<len(members)<=20 and len({member.name for member in members})==len(members))
        mapping={member.name:member for member in members}
        need("manifest.json" in mapping and all(member.isfile() and member.size<=32*1024*1024 and member.mode&0o022==0 for member in members))
        stream=archive.extractfile(mapping["manifest.json"]);need(stream is not None and mapping["manifest.json"].size<=65536)
        manifest=json.loads(stream.read())
        need(manifest.get("schema")=="tf-public-runtime-v1" and manifest.get("fingerprint")==stamp
            and manifest.get("abi")==abi_hash and manifest.get("platform")=="macos-26-intel"
            and manifest.get("source_commit")==source and manifest.get("run_id")==str(run))
        files=manifest.get("files");need(type(files) is dict and set(mapping)==set(files)|{"manifest.json"} and "tf_virtual_client" in files)
        total=0
        for name,value in files.items():
            need(allowed(name) and type(value) is dict and set(value)=={"bytes","sha256"})
            member=mapping[name];total+=member.size;need(total<=MAX and member.size==value["bytes"])
            reader=archive.extractfile(member);need(reader is not None)
            target=destination/name
            with target.open("xb") as output:shutil.copyfileobj(reader,output,1024*1024)
            need(sha(target)==value["sha256"]);target.chmod(0o755)
    return manifest
def pack():
    stamp=fingerprint();abi_hash=abi();root=Path("tf-sdk-build");files={}
    for path in sorted(root.iterdir()):
        if allowed(path.name):
            resolved=path.resolve();need(resolved.is_relative_to(root.resolve()) and resolved.is_file())
            files[path.name]={"bytes":resolved.stat().st_size,"sha256":sha(resolved)}
    need("tf_virtual_client" in files and 3<=len(files)<=19 and sum(item["bytes"] for item in files.values())<=MAX)
    manifest={"schema":"tf-public-runtime-v1","platform":"macos-26-intel","fingerprint":stamp,"abi":abi_hash,
        "source_commit":os.environ["GITHUB_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],"files":files}
    target=Path("tf-runtime-out/tf-runtime.tar.gz");target.parent.mkdir()
    with tarfile.open(target,"w:gz") as archive:
        raw=json.dumps(manifest,sort_keys=True).encode();entry=tarfile.TarInfo("manifest.json");entry.mode=0o644;entry.size=len(raw);archive.addfile(entry,io.BytesIO(raw))
        for name in files:
            data=(root/name).read_bytes();entry=tarfile.TarInfo(name);entry.mode=0o755;entry.size=len(data);archive.addfile(entry,io.BytesIO(data))
    unpack(target,Path("tf-runtime-relocated"),stamp,abi_hash,manifest["source_commit"],manifest["run_id"])
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:output.write("artifact=tf-public-runtime-"+stamp+"-"+abi_hash+"\n")
    print(json.dumps({"schema":"tf-public-runtime-pack-v1","fingerprint":stamp,"files":len(files)}))
def fetch():
    stamp=fingerprint();abi_hash=abi();api=GitHub(os.environ["GH_TOKEN"]);name="tf-public-runtime-"+stamp+"-"+abi_hash
    items=api.call("/actions/artifacts?per_page=20&name="+name).get("artifacts",[])
    for item in items:
        if item.get("name")!=name or item.get("expired") is not False:continue
        run=api.call("/actions/runs/"+str(item.get("workflow_run",{}).get("id")))
        if not (run.get("path")==WORKFLOW and run.get("head_branch")=="main" and run.get("status")=="completed"
                and run.get("conclusion")=="success" and run.get("head_sha")==item.get("workflow_run",{}).get("head_sha")):continue
        need(type(item.get("size_in_bytes")) is int and 0<item["size_in_bytes"]<=MAX and re.fullmatch(r"sha256:[a-f0-9]{64}",item.get("digest","")))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/"sealed.zip";api.archive(item["id"],archive,max_bytes=MAX);need("sha256:"+sha(archive)==item["digest"])
            with zipfile.ZipFile(archive) as zipped:
                need(len(zipped.infolist())==1 and zipped.namelist()==["tf-runtime.tar.gz"] and zipped.getinfo("tf-runtime.tar.gz").file_size<=MAX)
                packed=root/"runtime.tar.gz"
                with zipped.open("tf-runtime.tar.gz") as src,packed.open("xb") as dst:shutil.copyfileobj(src,dst,1024*1024)
            unpack(packed,Path("tf-sdk-build"),stamp,abi_hash,run["head_sha"],run["id"])
        print(json.dumps({"schema":"tf-public-runtime-fetch-v1","producer":run["id"],"fingerprint":stamp}));return
    raise ValueError("verified_TF_runtime_unavailable")
if __name__=="__main__":
    if sys.argv[1]=="pack":pack()
    else:fetch()
