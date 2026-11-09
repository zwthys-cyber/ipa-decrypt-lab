"""Bounded diagnosis of one CN app; emit only reviewed native categories."""
import json
import os
import re
import subprocess
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
    trace={}
    for line in raw.splitlines():
        match=re.fullmatch(r"IPA_CN_PURCHASE_(HTTP|FAILURE|STATUS):(-?[0-9]{1,7})",line)
        if match:
            code=int(match[2])
            if -999999<=code<=999999:trace[match[1].lower()]=code
        match=re.fullmatch(r"IPA_CN_PURCHASE_(MESSAGE|ACTION|SUCCESS_TYPE):(true|false)",line)
        if match:trace[match[1].lower()]=match[2]=="true"
        match=re.fullmatch(r"IPA_CN_PURCHASE_(PHASE|ROOT):(prepare_request|send_request|parse_response|dictionary|not_dictionary)",line)
        if match:trace[match[1].lower()]=match[2]
    entitlement={}
    kinds={"license","storefront","terms","account_setup","authentication","age","restriction","temporary","network_location","unavailable"}
    for line in raw.splitlines():
        match=re.fullmatch(r"IPA_CN_(PURCHASE|ENTITLEMENT)_MESSAGE_KINDS:([a-z_,]*)",line)
        if match:
            values=match[2].split(",") if match[2] else []
            if set(values)<=kinds:
                (trace if match[1]=="PURCHASE" else entitlement)["message_categories"]=values
        match=re.fullmatch(r"IPA_CN_(PURCHASE|ENTITLEMENT)_(HAS_FAILURE_TYPE|FAILURE_EMPTY|MESSAGE_EMPTY|MESSAGE|ACTION|SUCCESS_TYPE|APP_MATCH|VERSION_MATCH|BUNDLE_MATCH|DIALOG):(true|false)",line)
        if match:(trace if match[1]=="PURCHASE" else entitlement)[match[2].lower()]=match[3]=="true"
        match=re.fullmatch(r"IPA_CN_ENTITLEMENT_(HTTP|FAILURE|STATUS|ITEMS):(-?[0-9]{1,7})",line)
        if match and -999999<=int(match[2])<=999999:entitlement[match[1].lower()]=int(match[2])
    cleaned=subprocess.CompletedProcess([],result.returncode,
        "\n".join(line for line in (result.stdout or "").splitlines() if not line.startswith("IPA_CN_")),
        result.stderr or "")
    text=((cleaned.stdout or "")+"\n"+(cleaned.stderr or "")).lower()
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
            "classification":classify_download(cleaned),
            "diagnostic":safe_failure(cleaned),"native_error_codes":domains,"transport":authentication_diagnostics(cleaned),
            "purchase_trace":trace,"entitlement_trace":entitlement,"error_categories":matches,"stdout_bytes":len((result.stdout or "").encode()),"stderr_bytes":len((result.stderr or "").encode())}

def main():
    original=worker.run_download
    def probe(*args,**kwargs):
        result=original(*args,**kwargs)
        report=summarize(result)
        Path("cn-download-diagnostic.json").write_text(json.dumps(report))
        print(json.dumps(report),flush=True)
        if result.returncode==0 and os.environ.get("CN_LICENSE_CONTROL") not in ("existing_entitlement","response_control"):
            raise worker.ExportError("cn_diagnostic_download_succeeded")
        return result
    worker.run_download=probe
    try:code=worker.main(worker.export)
    finally:worker.run_download=original
    if os.environ.get("CN_LICENSE_CONTROL") in ("existing_entitlement","response_control"):
        if Path("cn-download-diagnostic.json").is_file():
            report=json.loads(Path("cn-download-diagnostic.json").read_text())
            report.update(control=os.environ.get("CN_LICENSE_CONTROL"),export_succeeded=code==0)
            if code==0:
                receipt=json.loads(Path("delivery-out/receipt.json").read_text())
                report.update(plaintext_verified=receipt.get("plaintext_verified") is True,
                              encrypted_images=receipt.get("encrypted_images"),decrypted_pages=receipt.get("decrypted_pages"))
            Path("cn-download-diagnostic.json").write_text(json.dumps(report))
            print(json.dumps(report),flush=True)
        return code
    return 0 if Path("cn-download-diagnostic.json").is_file() else code

if __name__=="__main__":raise SystemExit(main())
