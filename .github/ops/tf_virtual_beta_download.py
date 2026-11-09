"""Acquire the verified fixed TestFlight beta; publish only recipient ciphertext and closed proof."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import zipfile
from tf_virtual import public_env
from tf_virtual_invite_accept import seal,target

MAX=2*1024*1024*1024
KEYS={"schema","status","stage","downloaded","transport_removed","decryption_proven","archive_members",
      "encrypted_images","clear_images","downloaded_bytes","output_bytes","http_status","failure_category"}
def validate(value):
    if type(value) is not dict or set(value)!=KEYS:raise ValueError()
    if value["schema"]!="tf-beta-download-v1" or value["status"] not in {"failed","beta_downloaded"}:raise ValueError()
    if value["stage"] not in {"target_binding","download_and_transport","archive_received"}:raise ValueError()
    for key in ("downloaded","transport_removed","decryption_proven"):
        if type(value[key]) is not bool:raise ValueError()
    if value["decryption_proven"]:raise ValueError()
    bounds={"archive_members":1000000,"encrypted_images":100000,"clear_images":100000,
        "downloaded_bytes":MAX,"output_bytes":MAX,"http_status":599}
    if any(type(value[key]) is not int or not 0<=value[key]<=limit for key,limit in bounds.items()):raise ValueError()
    if value["failure_category"] not in {"none","rate_limited","download_or_metadata_failed","nonstandard_exception"}:raise ValueError()
    if value["status"]=="beta_downloaded" and not (value["downloaded"] and value["transport_removed"] and value["archive_members"]>0 and value["output_bytes"]>0):raise ValueError()
    return value

def digest(path):
    result=hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):result.update(block)
    return result.hexdigest()
def archive_binding(path,bundle):
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist();names=[item.filename for item in entries]
        if not 0<len(entries)<=1000000 or len(names)!=len(set(names)):raise ValueError()
        total=0
        for item in entries:
            name=item.filename;total+=item.file_size
            if name.startswith("/") or "\\" in name or ":" in name or ".." in name.split("/") or item.flag_bits&1:raise ValueError()
            if total>8*MAX or item.file_size>MAX:raise ValueError()
        infos=[name for name in names if name.startswith("Payload/") and name.endswith(".app/Info.plist") and name.count("/")==2]
        if len(infos)!=1:raise ValueError()
        info=plistlib.loads(archive.read(infos[0]))
        if info.get("CFBundleIdentifier")!=bundle:raise ValueError()
        executable=info.get("CFBundleExecutable")
        if type(executable) is not str or not executable or "/" in executable or "\\" in executable or executable=="..":raise ValueError()
        if infos[0].rsplit("/",1)[0]+"/"+executable not in names:raise ValueError()
        if archive.testzip() is not None:raise ValueError()
        return len(entries)
FIELDS={"url","dpInfo","sinf","data","status","error","messages","message","code","success","installUrl","installURL",
"downloadUrl","downloadURL","assetURL","assetData","assets","installMetadata","manifest","build","platform",
"installParameters","result","downloadInfo","softwareVersionExternalIdentifier","softwareVersionBundleId",
"softwareVersionBundleID","storefrontId","hasAcceptedTerms","termsAndConditions","isCompatible","compatible","reason"}
def response_shape(path):
    if not path.is_file() or path.stat().st_size>16*1024*1024:return {"present":False}
    try:root=json.loads(path.read_bytes())
    except Exception:return {"present":True,"parsed":False}
    nodes=[]
    def walk(value,depth=0):
        if depth>16 or len(nodes)>=64:return
        if type(value) is dict:
            nodes.append({"fields":{key:("null" if item is None else "bool" if type(item) is bool else
                "string_nonempty" if type(item) is str and item else "string_empty" if type(item) is str else
                "integer" if type(item) is int else "object" if type(item) is dict else "array" if type(item) is list else "other")
                for key,item in value.items() if key in FIELDS},"other_fields":min(100,len(set(value)-FIELDS))})
            for key,item in value.items():
                if key in FIELDS and type(item) in (dict,list):walk(item,depth+1)
        elif type(value) is list:
            for item in value[:16]:walk(item,depth+1)
    walk(root)
    return {"present":True,"parsed":True,"root_kind":"object" if type(root) is dict else "array" if type(root) is list else "other","nodes":nodes}

def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-beta-export-v1","status":"export_failed","run_id":env.get("GITHUB_RUN_ID"),
        "source_commit":env.get("GITHUB_SHA"),"invitation_accepted":False,"downloaded":False,
        "decryption_proven":False,"delivered":False,"existing_credentials_changed":False}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        from tf_virtual_invite_accept import RECIPIENT
        with tempfile.TemporaryDirectory(prefix="tf-beta-state-",dir=env["RUNNER_TEMP"]) as state_dir, tempfile.TemporaryDirectory(prefix="tf-beta-private-",dir=env["RUNNER_TEMP"]) as package_dir:
            root=Path(state_dir);root.chmod(0o700);output=Path(package_dir);output.chmod(0o700)
            restore(root,env)
            receipt["invitation_accepted"]=True
            try:
                _,bundle,_=target(root)
                result=subprocess.run([str(Path("tf-sdk-build/tf_virtual_client").resolve()),"--tf-download",str(root),str(output)],
                    capture_output=True,timeout=1500,env=public_env(env))
                if len(result.stdout)>4096:raise ValueError()
                native=validate(json.loads(result.stdout));receipt["result"]=native
                receipt["install_response_shape"]=response_shape(root/"tf-install-response.json")
                for metadata in output.glob(".testflight-download-*/install-metadata.json"):
                    if metadata.is_file() and not metadata.is_symlink() and metadata.stat().st_size<=16*1024*1024:
                        shutil.copyfile(metadata,root/"tf-install-metadata.json");(root/"tf-install-metadata.json").chmod(0o600)
                        break
                if result.returncode:raise ValueError()
                package=output/"beta.ipa"
                if not package.is_file() or not 0<package.stat().st_size<=MAX or package.stat().st_size!=native["output_bytes"]:raise ValueError()
                receipt["archive_members_verified"]=archive_binding(package,bundle)
                receipt["package_sha256"]=digest(package);receipt["package_bytes"]=package.stat().st_size
                with package.open("rb") as source,Path("tf-beta-package.age").open("wb") as destination:
                    encrypted=subprocess.run(["age","-r",RECIPIENT],stdin=source,stdout=destination,stderr=subprocess.PIPE,timeout=600,env=public_env(env))
                if encrypted.returncode:raise ValueError()
                sealed=Path("tf-beta-package.age")
                with sealed.open("rb") as stream:
                    if not stream.read(32).startswith(b"age-encryption.org/v1\n"):raise ValueError()
                receipt["package_cipher_sha256"]=digest(sealed);receipt["package_cipher_bytes"]=sealed.stat().st_size
                receipt["downloaded"]=True;receipt["status"]="beta_downloaded_content_encryption_unverified"
            finally:seal(root,env,receipt)
    except Exception:pass
    if not receipt["downloaded"]:Path("tf-beta-package.age").unlink(missing_ok=True)
    Path("tf-beta-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["downloaded"] else 2
if __name__=="__main__":raise SystemExit(main())
