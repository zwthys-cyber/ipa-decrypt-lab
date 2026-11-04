"""Same-runner enrollment, original download, candidate model recovery and verification."""
import argparse
import base64
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile

from machine_enrollment import trial as enroll, run_private
from native_store import run as store_run, classify, classify_download
from store_download import metadata
from private_trial import extract_checked
from offline_verify import verify, MODEL_LIMIT

TARGET = "6599842047"


def base():
    return dict(schema="ipa-lab-model-bootstrap-v1", status="not_started",
                model_recovered=False, decryption_proven=False, plaintext_verified=False,
                runtime_verified=False, model_plaintext_published=False, plaintext_retained=False)


def state_ready(result):
    return (type(result) is dict and result.get("store_session_authenticated") is True
            and result.get("authorization_request_attempted") is True
            and result.get("http_status")==200 and result.get("apple_failure_present") is False
            and result.get("keybag_present") is True and result.get("commerce_import_call_returned") is True
            and result.get("state_observation_after",{}).get("root_status")=="observed"
            and result.get("state_observation_after",{}).get("root",{}).get("files",{}).get("fpsd_sidb",{}).get("status")=="regular_nonempty")


def download_original(binary, ipa):
    email,password=os.environ.get("APPLE_ID"),os.environ.get("APPLE_PASSWORD")
    env={k:os.environ[k] for k in ("PATH","HOME","LANG","LAB_KBSYNC_HELPER") if k in os.environ}
    env.update(GITHUB_ACTIONS="true",APPLEPACKAGE_PASSWORD=password or "")
    try:
        info=metadata(TARGET)
        result=store_run(binary,["login",email],env)
        if classify(result)!="authenticated":
            return "download_login_failed"
        result=store_run(binary,["download",email,info["bundleId"],"--output",str(ipa)],env)
        if result.returncode or not ipa.is_file() or not 0<ipa.stat().st_size<=1024**3:
            return classify_download(result)
        return "original_downloaded"
    finally:
        try:
            store_run(binary,["logout",email],env)
        except Exception:
            pass


def candidate_app(ipa, root):
    extract_checked(ipa,root)
    apps=list((root/"Payload").glob("*.app"))
    if len(apps)!=1 or not apps[0].is_dir():
        raise ValueError("main_app_unavailable")
    info_path=apps[0]/"Info.plist"
    if not info_path.is_file() or info_path.stat().st_size>1024**2:
        raise ValueError("app_metadata_unavailable")
    info=plistlib.loads(info_path.read_bytes())
    executable=info.get("CFBundleExecutable")
    if (type(executable) is not str or not executable or "/" in executable or "\\" in executable
            or executable in {".",".."} or not (apps[0]/executable).is_file()):
        raise ValueError("app_executable_unavailable")
    if not (apps[0]/"SC_Info").is_dir():
        raise ValueError("app_license_unavailable")
    return apps[0]


def setup_summary(raw, root):
    if len(raw)>1024**2:
        raise ValueError("invalid_setup_report")
    value=json.loads(raw)
    if (type(value) is not dict or value.get("schema")!="unfairplay-setup-v1"
            or value.get("success") is not True or type(value.get("plaintext_verified")) is not bool
            or type(value.get("encrypted_images")) is not int or not 0<value["encrypted_images"]<=4096
            or type(value.get("decrypted_pages")) is not int or not 0<value["decrypted_pages"]<=1024**2):
        raise ValueError("invalid_setup_report")
    path=Path(value.get("model",""))
    resolved=path.resolve(strict=True)
    if (not path.is_absolute() or path.is_symlink() or not resolved.is_relative_to(root.resolve())
            or not resolved.is_file() or not 0<resolved.stat().st_size<=MODEL_LIMIT
            or resolved.stat().st_mode&0o077):
        raise ValueError("invalid_private_model")
    return resolved,dict(setup_plaintext_verified=value["plaintext_verified"],
                         setup_encrypted_images=value["encrypted_images"],
                         setup_decrypted_pages=value["decrypted_pages"])


def recovery_failure(raw):
    text=raw[:1024**2].decode("utf-8","replace").lower()
    return {word:word in text for word in ("sidb","sinf","supf","supp","selector","authentication",
                                           "permission","current layout","unsupported","hash","hardware")}


def sealed_summary(raw):
    if len(raw)>64*1024:
        raise ValueError("invalid_sealed_model")
    value=json.loads(raw)
    if (type(value) is not dict or value.get("schema")!="ipa-lab-github-sealed-model-v1"
            or value.get("repository")!="zwthys-cyber/ipa-decrypt-lab"
            or value.get("secret_name")!="FAIRPLAY_MODEL_B64"
            or value.get("key_id")!="3380204578043523366"):
        raise ValueError("invalid_sealed_model")
    cipher=base64.b64decode(value.get("encrypted_value",""),validate=True)
    if not 48<len(cipher)<=44*1024+48:
        raise ValueError("invalid_sealed_model")
    return {key:value[key] for key in ("schema","repository","secret_name","key_id","encrypted_value")}


def bootstrap(login_binary,native_binary,download_binary,engine,sealer,report=None):
    report=base() if report is None else report
    result=enroll(login_binary,native_binary,backend="commerce",session_context="cookies",
                  client_context="login_agent",observe_state=True)
    report["enrollment"]=result
    if not state_ready(result):
        return dict(report,status="enrollment_state_unavailable")
    with tempfile.TemporaryDirectory(prefix="ipa-lab-model-bootstrap-") as directory:
        root=Path(directory)
        root.chmod(0o700)
        ipa=root/"original.ipa"
        report["download_status"]=download_original(download_binary,ipa)
        if report["download_status"]!="original_downloaded":
            return dict(report,status="original_download_failed")
        report["original_downloaded"]=True
        app=candidate_app(ipa,root/"candidate")
        # This is an extracted candidate, never represented as an installed/running app.
        report["app_input_kind"]="extracted_ipa_candidate"
        model_dir=root/"models"
        model_dir.mkdir(mode=0o700)
        env={"PATH":"/usr/bin:/bin","GITHUB_ACTIONS":"true"}
        argv=["/usr/bin/sudo","-n","--","/usr/bin/env","-i","PATH=/usr/bin:/bin",
              "GITHUB_ACTIONS=true","TMPDIR="+str(root),"SUDO_UID="+str(os.getuid()),
              "SUDO_GID="+str(os.getgid()),engine,"setup","--app",str(app),"--ipa",str(ipa),
              "--model-dir",str(model_dir)]
        try:
            code,out,err=run_private(argv,env,timeout=300)
        except subprocess.TimeoutExpired:
            return dict(report,status="model_recovery_timeout")
        if code:
            return dict(report,status="model_recovery_rejected",recovery_mentions=recovery_failure(out+err))
        model,summary=setup_summary(out,model_dir)
        report.update(summary)
        report["model_recovered"]=True
        previous=os.environ.get("FAIRPLAY_MODEL_B64")
        try:
            os.environ["FAIRPLAY_MODEL_B64"]=base64.b64encode(model.read_bytes()).decode("ascii")
            checked=verify(engine,ipa)
        finally:
            if previous is None:
                os.environ.pop("FAIRPLAY_MODEL_B64",None)
            else:
                os.environ["FAIRPLAY_MODEL_B64"]=previous
        report["verification"]=checked
        if checked.get("decryption_proven") is not True or checked.get("plaintext_verified") is not True:
            return dict(report,status="model_plaintext_not_verified")
        code,out,_=run_private([sealer,str(model)],env,timeout=15)
        if code:
            return dict(report,status="model_sealing_failed",decryption_proven=True,plaintext_verified=True)
        report["sealed_model"]=sealed_summary(out)
        return dict(report,status="model_recovered_and_verified",decryption_proven=True,plaintext_verified=True)


def main():
    parser=argparse.ArgumentParser()
    for option in ("login-binary","native-binary","download-binary","engine","sealer"):
        parser.add_argument("--"+option,required=True)
    args=parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS")!="true" or sys.platform!="darwin":
        raise SystemExit("GitHub-hosted macOS required")
    if not os.environ.get("APPLE_ID") or not os.environ.get("APPLE_PASSWORD"):
        report=dict(base(),status="missing_credentials")
    else:
        report=base()
        try:
            report=bootstrap(*(str(Path(getattr(args,key)).resolve()) for key in
                               ("login_binary","native_binary","download_binary","engine","sealer")),report=report)
        except subprocess.TimeoutExpired:
            report["status"]="bootstrap_timeout_do_not_retry"
        except Exception:
            report["status"]="bootstrap_failed_do_not_retry"
    sealed=report.pop("sealed_model",None)
    if sealed is not None:
        print(json.dumps(sealed,sort_keys=True))
        report["sealed_model_emitted"]=True
    print(json.dumps(report,sort_keys=True))
    return 0 if report["status"]=="model_recovered_and_verified" else 2


if __name__=="__main__":
    raise SystemExit(main())
