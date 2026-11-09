"""Offline doctor for the exact beta and saved CN model; only closed checks leave the runner."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
from tf_virtual_beta_verify import restore_package
from tf_virtual_invite_accept import target,seal
from tf_virtual_beta_download import archive_binding
from tf_virtual import public_env

CHECKS={"ipa_inventory","ipa_sinf","current_sinf_layout","model_valid","selector_match","sinf_model_validation"}
def closed(value):
    if type(value) is not dict or value.get("schema")!="unfairplay-doctor-v1":raise ValueError()
    checks=value.get("checks")
    if type(checks) is not dict:raise ValueError()
    result={key:checks[key] for key in CHECKS if type(checks.get(key)) is bool}
    result.update(sinf_count=min(1024,len(value.get("sinf",[]))),model_count=min(256,len(value.get("models",[]))),
        error_count=min(1024,len(value.get("errors",[]))))
    return result

def classify(note):
    for text,category in (
        ("encrypted source fails CodeDirectory","encrypted_source_signature_mismatch"),
        ("plaintext page hash mismatch","plaintext_hash_mismatch"),
        ("mutation escaped FairPlay range","mutation_scope_failed"),
        ("pre-encryption table is invalid or truncated","pre_encryption_table_invalid"),
        ("refusing to replace","output_policy_rejected"),
        ("permission denied","file_permission_rejected"),
        ("unsupported encrypted Mach-O","unsupported_macho"),
        ("CodeDirectory","signature_structure_rejected")):
        if text in note:return category
    return "other"

def main():
    env=dict(os.environ);os.umask(0o077)
    receipt={"schema":"tf-beta-model-diagnostic-v1","status":"inspection_failed","apple_requests":0,
        "authorization_attempted":False,"decryption_proven":False,"delivered":False,
        "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA")}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-doctor-state-") as state_dir,tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-doctor-package-") as package_dir:
            state=Path(state_dir);state.chmod(0o700);root=Path(package_dir);root.chmod(0o700);restore(state,env)
            try:
                _,bundle,_=target(state);package=restore_package(root,env,receipt);archive_binding(package,bundle)
                raw=base64.b64decode(env["FAIRPLAY_CN_MODEL_B64"],validate=True)
                if len(raw)!=4184 or raw[:8]!=b"FPSENR2\x00":raise ValueError()
                model=root/"model.bin";model.write_bytes(raw);model.chmod(0o600)
                result=subprocess.run([str(Path("cn-runtime/offline-engine").resolve()),"doctor","--ipa",str(package),
                    "--model",str(model)],capture_output=True,timeout=180,env=public_env(env))
                if len(result.stdout)>8*1024**2 or len(result.stderr)>32768:raise ValueError()
                (state/"tf-model-diagnostic.json").write_bytes(result.stdout);(state/"tf-model-diagnostic.json").chmod(0o600)
                (state/"tf-model-diagnostic-error.txt").write_bytes(result.stderr);(state/"tf-model-diagnostic-error.txt").chmod(0o600)
                receipt["checks"]=closed(json.loads(result.stdout))
                verified=subprocess.run([str(Path("cn-runtime/offline-engine").resolve()),"verify","--input",str(package),
                    "--model",str(model)],capture_output=True,timeout=180,env=public_env(env))
                if len(verified.stdout)>1024**2 or len(verified.stderr)>32768:raise ValueError()
                (state/"tf-model-verification.json").write_bytes(verified.stdout);(state/"tf-model-verification.json").chmod(0o600)
                (state/"tf-model-verification-error.txt").write_bytes(verified.stderr);(state/"tf-model-verification-error.txt").chmod(0o600)
                receipt["verification_exit_success"]=verified.returncode==0
                receipt["verification_failure"]=classify(verified.stderr.decode("utf-8","replace")) if verified.returncode else "none"
                if verified.returncode==0:
                    from offline_verify import sanitized_report
                    from ipa_audit import audit
                    receipt["verification"]=sanitized_report(json.loads(verified.stdout),audit(package)["encrypted_slice_count"])
                    receipt["decryption_proven"]=receipt["verification"]["decryption_proven"]
                receipt["stage"]="offline_doctor";receipt["status"]="inspection_complete"
            finally:seal(state,env,receipt)
    except Exception:pass
    Path("tf-beta-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="inspection_complete" else 2
if __name__=="__main__":raise SystemExit(main())
