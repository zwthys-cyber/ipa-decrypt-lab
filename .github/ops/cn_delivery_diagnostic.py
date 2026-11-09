"""Bounded diagnosis of one CN app; emit only reviewed native categories."""
import json
import re
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
import cn_private_export as worker
from native_store import download_diagnostics,classify_download,authentication_diagnostics
from cn_download_probe import safe_failure

def summarize(result):
    raw=(result.stdout or "")+"\n"+(result.stderr or "")
    domains={}
    for domain in ("StoreAMD","LabKBSyncFailed","LabEntEndpointMissing","LabEntResponse","LabPurchaseUnconfirmed","NSURLErrorDomain"):
        found=re.findall(re.escape(domain)+r"(?: error |, Code=| code: )(-?[0-9]{1,5})(?![0-9])",raw)
        if found:domains[domain]=int(found[-1])
    text=raw.lower()
    patterns={
        "invalid_purchase_response":"invalid purchase response",
        "purchase_failed":"purchase failed",
        "request_failed":"request failed with status",
        "response_empty":"response body is empty",
        "invalid_response":"invalid response",
        "no_response":"no response received",
        "redirect_missing":"failed to retrieve redirect location",
        "temporarily_unavailable":"item is temporarily unavailable",
        "subscription_required":"subscription required",
        "decoding_error":"datacorrupted",
        "invalid_plist":"not in the correct format",
        "network_error":"nsurlerrordomain",
        "tls_error":"ssl error",
        "client_argument_error":"unexpected argument",
        "signature_error":"sapsigner",
    }
    matches=[name for name,pattern in patterns.items() if pattern in text]
    return {"schema":"cn-download-diagnostic-v1","app_id":"1142110895",
            "download_succeeded":result.returncode==0,
            "classification":classify_download(result),
            "diagnostic":safe_failure(result),"native_error_codes":domains,"transport":authentication_diagnostics(result),
            "error_categories":matches,"stdout_bytes":len((result.stdout or "").encode()),"stderr_bytes":len((result.stderr or "").encode())}

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
