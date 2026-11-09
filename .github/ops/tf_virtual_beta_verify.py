"""Model-only verification/export of one pinned TestFlight beta; no Apple account requests."""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from telegram_queue import GitHub
from private_export import export_original,ExportError
from tf_virtual_beta_download import digest,archive_binding
from tf_virtual_invite_accept import target,seal
from tf_virtual import public_env

RUN=42698306052
SOURCE="2fe05dc279008872e24a4ad83576bb6973d87d5f"
ARCHIVE="8f289ac5f7997093de89788d9edd435ca4775176155de74ee5c2d5b54cdd5893"
CIPHER="09c5471fd2c4a9a4a17d346d917133e5e613019ac93baaa9a52c7ab19604fa68"
def need(value):
    if not value:raise ValueError()
def restore_package(root,env):
    api=GitHub(env["GH_TOKEN"])
    run=api.call("/actions/runs/"+str(RUN))
    need(run.get("head_sha")==SOURCE and run.get("head_branch")=="main" and run.get("run_attempt")==1
        and run.get("status")=="completed" and run.get("conclusion")=="success"
        and run.get("path")==".github/workflows/testflight-virtual.yml")
    items=api.call("/actions/runs/"+str(RUN)+"/artifacts?per_page=100")["artifacts"]
    found=[item for item in items if item.get("name")=="tf-beta-download-"+str(RUN)+"-attempt-1" and not item.get("expired")]
    need(len(found)==1);item=found[0]
    need(item.get("digest")=="sha256:"+ARCHIVE and 0<item.get("size_in_bytes",0)<=2*1024**3)
    path=root/"sealed.zip";api.archive(item["id"],path,max_bytes=2*1024**3)
    need(digest(path)==ARCHIVE)
    with zipfile.ZipFile(path) as archive:
        need(len(archive.infolist())==3 and set(archive.namelist())=={"tf-beta-package.age","tf-accept-state.age","tf-beta-receipt.json"})
        need(archive.getinfo("tf-beta-receipt.json").file_size<=65536)
        receipt=json.loads(archive.read("tf-beta-receipt.json"))
        need(receipt.get("source_commit")==SOURCE and receipt.get("run_id")==str(RUN)
            and receipt.get("downloaded") is True and receipt.get("invitation_accepted") is True
            and receipt.get("decryption_proven") is False and receipt.get("package_cipher_sha256")==CIPHER)
        info=archive.getinfo("tf-beta-package.age")
        need(0<info.file_size<=2*1024**3 and info.file_size==receipt.get("package_cipher_bytes"))
        cipher=root/"package.age"
        with archive.open(info) as source,cipher.open("xb") as dest:shutil.copyfileobj(source,dest,1024*1024)
    need(digest(cipher)==CIPHER)
    key=root/"key.txt";key.write_text(env["DELIVERY_AGE_IDENTITY"]);key.chmod(0o600)
    package=root/"original.ipa"
    try:
        with cipher.open("rb") as source,package.open("xb") as dest:
            result=subprocess.run(["age","-d","-i",str(key)],stdin=source,stdout=dest,stderr=subprocess.PIPE,timeout=600,env=public_env(env))
        need(result.returncode==0 and package.stat().st_size==receipt["package_bytes"] and digest(package)==receipt["package_sha256"])
    finally:key.unlink(missing_ok=True);cipher.unlink(missing_ok=True);path.unlink(missing_ok=True)
    return package

def main():
    env=dict(os.environ);os.umask(0o077)
    receipt={"schema":"tf-beta-model-export-v1","status":"export_failed","run_id":env.get("GITHUB_RUN_ID"),
        "source_commit":env.get("GITHUB_SHA"),"input_run":str(RUN),"apple_requests":0,
        "authorization_attempted":False,"model_reused":False,"decryption_proven":False,"delivered":False}
    try:
        need(env.get("GITHUB_ACTIONS")=="true")
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-model-state-") as state_dir,tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-model-package-") as package_dir:
            state=Path(state_dir);state.chmod(0o700);root=Path(package_dir);root.chmod(0o700)
            restore(state,env)
            try:
                _,bundle,identifier=target(state)
                original=restore_package(root,env);archive_binding(original,bundle);receipt["input_verified"]=True
                need(env.get("FAIRPLAY_CN_MODEL_B64"))
                os.environ["FAIRPLAY_MODEL_B64"]=env["FAIRPLAY_CN_MODEL_B64"]
                receipt["model_reused"]=True
                def progress(stage):pass
                try:
                    result=export_original(str(Path("cn-runtime/offline-engine").resolve()),
                        str(Path("cn-runtime/delivery-crypt").resolve()),root,original,{"bundleId":bundle},
                        identifier,"tf-yoNuHexZ-"+env["GITHUB_RUN_ID"],
                        "age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d",
                        Path("tf-model-export"),progress,profile="cn")
                finally:os.environ.pop("FAIRPLAY_MODEL_B64",None)
                receipt.update(status="beta_plaintext_verified",decryption_proven=True,
                    encrypted_images=result["encrypted_images"],decrypted_pages=result["decrypted_pages"])
            finally:
                note=root/"private-report.json"
                if note.is_file() and not note.is_symlink() and note.stat().st_size<=8*1024**2:
                    shutil.copyfile(note,state/"tf-decrypt-report.json");(state/"tf-decrypt-report.json").chmod(0o600)
                seal(state,env,receipt)
    except ExportError as error:
        receipt["status"]="model_export_rejected"
        if str(error) in {"decryption_rejected","unverified_plaintext","missing_plaintext_hashes","plaintext_hash_mismatch","no_encrypted_images","output_inventory_mismatch"}:receipt["failure_category"]=str(error)
    except Exception:pass
    Path("tf-beta-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["decryption_proven"] else 2
if __name__=="__main__":raise SystemExit(main())
