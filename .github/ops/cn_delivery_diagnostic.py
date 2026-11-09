"""Bounded diagnosis of one CN app; emit only reviewed native categories."""
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import cn_private_export as worker
from native_store import download_diagnostics,classify_download
from cn_download_probe import safe_failure

def summarize(result):
    raw=(result.stdout or "")+"\n"+(result.stderr or "")
    domains={}
    for domain in ("StoreAMD","LabKBSyncFailed","LabEntEndpointMissing","LabEntResponse","LabPurchaseUnconfirmed","NSURLErrorDomain"):
        found=re.findall(re.escape(domain)+r"(?: error |, Code=| code: )(-?[0-9]{1,5})(?![0-9])",raw)
        if found:domains[domain]=int(found[-1])
    return {"schema":"cn-download-diagnostic-v1","app_id":"1142110895",
            "download_succeeded":result.returncode==0,
            "classification":classify_download(result),
            "diagnostic":safe_failure(result),"native_error_codes":domains}

def main():
    original=worker.run_download
    def probe(*args,**kwargs):
        result=original(*args,**kwargs)
        report=summarize(result)
        Path("cn-download-diagnostic.json").write_text(json.dumps(report))
        print(json.dumps(report),flush=True)
        if result.returncode==0:
            raise worker.ExportError("cn_diagnostic_download_succeeded")
        return result
    worker.run_download=probe
    try:code=worker.main(worker.export)
    finally:worker.run_download=original
    return 0 if Path("cn-download-diagnostic.json").is_file() else code

if __name__=="__main__":raise SystemExit(main())
