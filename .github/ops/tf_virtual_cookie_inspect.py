"""Offline inspection of one pinned sealed Store response; no Apple account/network inputs."""
import json
import os
import plistlib
from pathlib import Path
import subprocess
import tempfile
from tf_virtual import public_env

FIELDS={"count","name_bad","value_bad","domain_bad","path_bad","expiry_kind_bad","host_flag_kind_bad"}
def validate(value):
    if type(value) is not dict or set(value)!={"schema","before","after","original_failure","response_binding","network_requests"}:raise ValueError()
    if value["schema"]!="tf-cookie-inspection-v1":raise ValueError()
    if value["original_failure"] not in {"invalid_saved_cookie","invalid_cookie_container","other"}:raise ValueError()
    if value["response_binding"] is not True or type(value["network_requests"]) is not int or value["network_requests"]!=0:raise ValueError()
    for key in ("before","after"):
        item=value[key]
        if type(item) is not dict or set(item)!=FIELDS:raise ValueError()
        if any(type(v) is not int or not 0<=v<=256 for v in item.values()):raise ValueError()
        if any(item[name]>item["count"] for name in FIELDS-{"count"}):raise ValueError()
    return value

def capture_shape(root):
    names=("failure.txt","store-auth-meta.json","store-auth-response.bin")
    result={"failure_present":(root/names[0]).is_file(),"meta_present":(root/names[1]).is_file(),
            "body_present":(root/names[2]).is_file(),"response_headers_kind":"other",
            "request_headers_kind":"other","id_header_present":False,"id_matches":False,
            "status_zero":False,"cookie_header_count":0,"original_failure":"other"}
    if not all((root/n).is_file() for n in names):return result
    text=(root/names[0]).read_text()
    result["original_failure"]="invalid_saved_cookie" if text=="Invalid saved Store cookie" else "invalid_cookie_container" if text=="Invalid Store cookies" else "other"
    meta=json.loads((root/names[1]).read_bytes())
    response=meta.get("response_headers");request=meta.get("request_headers")
    result["response_headers_kind"]="list" if type(response) is list else "dict" if type(response) is dict else "other"
    result["request_headers_kind"]="list" if type(request) is list else "dict" if type(request) is dict else "other"
    if type(request) is dict:
        result["id_header_present"]="X-DSID" in request
    if type(response) is list:
        result["cookie_header_count"]=min(256,sum(1 for item in response if type(item) is list and len(item)==2 and type(item[0]) is str and item[0].lower()=="set-cookie"))
    raw=(root/names[2]).read_bytes()
    begin=raw.find(b"<plist");end=raw.find(b"</plist>")
    if begin>=0 and end>begin:raw=raw[begin:end+8]
    data=plistlib.loads(raw)
    if type(data) is dict and type(request) is dict:
        result["id_matches"]=str(data.get("dsPersonId"))==request.get("X-DSID")
        result["status_zero"]=type(data.get("status")) is int and data["status"]==0
    return result

def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-cookie-probe-v1","status":"inspection_failed",
             "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA"),"stage":"initialization"}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(prefix="tf-cookie-offline-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700)
            receipt["stage"]="restore"
            restore(root,env)
            receipt["stage"]="capture_shape"
            receipt["capture_shape"]=capture_shape(root)
            receipt["stage"]="native_inspection"
            result=subprocess.run([str(Path("tf-sdk-build/tf_virtual_client").resolve()),"--cookie-inspect",str(root)],
                capture_output=True,timeout=30,env=public_env(env))
            receipt["native_exit"]=max(0,min(255,result.returncode))
            if len(result.stdout)>4096:raise ValueError()
            if result.returncode:
                from tf_virtual import validate as validate_auth
                receipt["native_failure"]=validate_auth(json.loads(result.stdout))
                raise ValueError()
            receipt["stage"]="summary_validation"
            receipt["result"]=validate(json.loads(result.stdout))
            receipt["status"]="inspection_verified"
    except Exception:
        pass
    Path("tf-cookie-inspection.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="inspection_verified" else 2
if __name__=="__main__":raise SystemExit(main())
