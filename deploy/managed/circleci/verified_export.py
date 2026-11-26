"""Full existing plaintext proofs followed by standard age encryption on CircleCI."""
import base64
import json
import os
from pathlib import Path
import struct
import re
from app_presentation import filename as delivery_filename
from task_context import RECIPIENT, minimal_env, require
from private_export import audit, validate_report, scrub_archive, verify_output, verify_version, digest
from capacity import MAX_IPA_BYTES, DECRYPT_TIMEOUT, CRYPTO_TIMEOUT

def model_bytes(encoded):
    require(type(encoded) is str and len(encoded)<=44000,"export_model_encoding")
    value=base64.b64decode(encoded,validate=True)
    require(len(value)==4184 and value[:8]==b"FPSENR2\x00" and
        struct.unpack_from("<II",value,8)==(2,len(value)),"export_model_format")
    return value

def export_original(task,engine,age,root,original,info,model,output,env,runner,stage,
                    version_id="",resolved_version="",delivery=None):
    root=Path(root);original=Path(original);output=Path(output)
    require(not original.is_symlink() and original.is_file() and
        0<original.stat().st_size<=MAX_IPA_BYTES,"export_source_size")
    require(not output.exists() and not output.is_symlink() and task["recipient"]==RECIPIENT,"export_destination")
    stage("auditing")
    before=audit(original)
    require(before["bundle_id"]==info["bundleId"],"downloaded_app_mismatch")
    verify_version(before,task["version"],resolved_version)
    model_path=root/"model.bin"
    with os.fdopen(os.open(model_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"wb") as stream:
        stream.write(model_bytes(model))
    candidate,cleaned,sealed,report_path=(root/x for x in ("candidate.ipa","delivery.ipa","package.ipa.age","private-report.json"))
    child_home=root/"engine-home";child_home.mkdir(mode=0o700)
    child=minimal_env(env,child_home)
    stage("decrypting")
    result=runner(engine,["decrypt","--input",original,"--output",candidate,"--report",report_path,
        "--model",model_path,"--strip-account-data"],child,DECRYPT_TIMEOUT)
    require(result.returncode==0 and candidate.is_file() and not candidate.is_symlink() and
        report_path.is_file() and not report_path.is_symlink() and
        report_path.stat().st_size<=8*1024*1024,"decryption_rejected")
    stage("verifying")
    report=json.loads(report_path.read_bytes())
    images,pages=validate_report(report,before,candidate)
    # The portable reference streams bounded chunks and does not call GitHub-only delivery-crypt.
    scrub_archive(candidate,cleaned)
    verified=verify_output(cleaned,before)
    verify_version(verified,task["version"],resolved_version)
    plain_size,plain_digest=cleaned.stat().st_size,digest(cleaned)
    stage("encrypting")
    result=runner(age,["--encrypt","--recipient",RECIPIENT,"--output",sealed,cleaned],child,CRYPTO_TIMEOUT)
    require(result.returncode==0 and sealed.is_file() and not sealed.is_symlink() and
        0<sealed.stat().st_size<=MAX_IPA_BYTES+2*1024*1024,"delivery_encryption_failed")
    with sealed.open("rb") as stream:
        require(stream.read(22)==b"age-encryption.org/v1\n","delivery_encryption_format")
    receipt=dict(schema="circleci-private-delivery-v1",status="encrypted_artifact_ready",provider="circleci",
        job_id=task["job_id"],request_id=task["request_id"],run_id=task["run_id"],
        worker_job_id=task["worker_job_id"],source_commit=task["source_sha"],account_profile=task["profile"],
        app_id=str(info.get("trackId",task["target"])),requested_version=task["version"],resolved_version=resolved_version,
        external_version_id=version_id,plaintext_verified=True,runtime_verified=False,
        account_data_removed=True,plaintext_published=False,encrypted_images=images,decrypted_pages=pages,
        plaintext_bytes=plain_size,plaintext_sha256=plain_digest,ciphertext_bytes=sealed.stat().st_size,
        ciphertext_sha256=digest(sealed),recipient=RECIPIENT)
    receipt["filename"]=delivery_filename({"display_name":info.get("trackName") or info["bundleId"],
        "version":verified.get("version") or resolved_version},receipt["app_id"],testflight=task["profile"]=="tf")
    receipt["filename"]="".join(c if c.isalnum() or c in " ._()-" else "_" for c in receipt["filename"])
    require(1<=len(receipt["filename"])<=160 and not receipt["filename"].startswith("."),"delivery_filename")
    if task["profile"]=="tf":
        receipt.update(target_type="testflight",testflight_invite=task["target"])
    if delivery is not None:
        stage("uploading_private")
        deposited=delivery(cleaned,receipt)
        require(type(deposited) is dict and set(deposited)=={"file_id","filename","bytes","sha256"} and
            re.fullmatch(r"[A-Za-z0-9_-]{10,160}",deposited.get("file_id","")) and
            deposited["filename"]==receipt["filename"] and deposited["bytes"]==plain_size and
            deposited["sha256"]==plain_digest,"private_delivery_binding")
        receipt["private_delivery"]=deposited
    stage("publishing_ciphertext")
    created=False
    try:
        output.mkdir(mode=0o700);created=True
        sealed.replace(output/"package.ipa.age")
        with os.fdopen(os.open(output/"receipt.json",os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"w") as stream:
            json.dump(receipt,stream,sort_keys=True);stream.write("\n")
        stage("ciphertext_verified")
    except BaseException:
        if created:
            import shutil
            shutil.rmtree(output,ignore_errors=True)
        raise
    return receipt
