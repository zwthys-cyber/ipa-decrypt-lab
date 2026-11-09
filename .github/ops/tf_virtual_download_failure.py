"""Offline closed classification of the fixed encrypted download failure; no Apple calls."""
import json
import os
from pathlib import Path
import tempfile
from tf_virtual_download_failure_restore import restore

ERRORS={
"TestFlight returned no available iOS build":"no_available_ios_build",
"TestFlight returned incomplete install metadata":"incomplete_install_metadata",
"TestFlight reported an API error":"api_error",
"Application is absent from the iOS TestFlight catalog":"app_absent",
"Invalid TestFlight context size":"context_invalid",
"TestFlight session requires hardware20":"hardware_invalid",
}
def classify(note):
    for fixed,category in ERRORS.items():
        if note==fixed:return category
    if "json.exception.type_error" in note:return "json_type_error"
    if "json.exception.out_of_range" in note:return "json_missing_field"
    if "json.exception.parse_error" in note:return "json_parse_error"
    if note.startswith("TestFlight request rejected (HTTP "):return "http_rejected"
    return "other"

def main():
    env=dict(os.environ);os.umask(0o077)
    receipt={"schema":"tf-download-failure-v1","status":"inspection_failed","apple_requests":0,"downloaded":False,"decryption_proven":False}
    try:
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-download-inspect-") as folder:
            root=Path(folder);root.chmod(0o700);restore(root,env)
            path=root/"download-failure.txt"
            if not path.is_file() or path.stat().st_size>32768:raise ValueError()
            receipt["failure_category"]=classify(path.read_text())
            receipt["install_metadata_present"]=(root/"tf-install-metadata.json").is_file()
            receipt["status"]="inspection_complete"
    except Exception:pass
    Path("tf-beta-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="inspection_complete" else 2
if __name__=="__main__":raise SystemExit(main())
