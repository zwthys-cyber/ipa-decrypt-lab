"""Offline inspection of one pinned sealed Store response; no Apple account/network inputs."""
import json
import os
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

def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-cookie-probe-v1","status":"inspection_failed",
             "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA")}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(prefix="tf-cookie-offline-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700)
            restore(root,env)
            result=subprocess.run([str(Path("tf-sdk-build/tf_virtual_client").resolve()),"--cookie-inspect",str(root)],
                capture_output=True,timeout=30,env=public_env(env))
            if result.returncode or len(result.stdout)>4096:raise ValueError()
            receipt["result"]=validate(json.loads(result.stdout))
            receipt["status"]="inspection_verified"
    except Exception:
        pass
    Path("tf-cookie-inspection.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="inspection_verified" else 2
if __name__=="__main__":raise SystemExit(main())
