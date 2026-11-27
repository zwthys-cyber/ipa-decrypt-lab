"""GitHub-only one-shot public CircleCI producer request, after adapter contracts."""
import json
import os
from pathlib import Path
import re
import sys
import time
from probe import api, validate_run, require, uuid, REPO, BRANCH
DEFINITION="ed763fe9-befd-4122-83df-30f5d94bb94b"

def main():
    receipt=dict(schema="circleci-native-request-v1",status="not_submitted",private_credentials=False)
    def save():Path("circleci-native-request.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
    try:
        require(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("GITHUB_REPOSITORY")==REPO and
            os.environ.get("GITHUB_REF")=="refs/heads/"+BRANCH and os.environ.get("GITHUB_RUN_ATTEMPT")=="1",
            "native_request_context")
        source=os.environ.get("GITHUB_SHA","");require(re.fullmatch(r"[a-f0-9]{40}",source),"native_request_source")
        token=os.environ.get("CIRCLECI_API_TOKEN","");require(len(token)>=16,"native_request_credentials")
        mode=os.environ.get("NATIVE_REQUEST_MODE","producer")
        require(mode in ("producer","consumer"),"native_request_mode")
        receipt.update(status="intent",source=source,mode=mode);save()
        code,value=api(token,"/runs",dict(data=dict(attributes=dict(config=dict(branch=BRANCH),
            checkout=dict(branch=BRANCH),parameters=dict(dispatch_probe=False,build_native_runtime=mode=="producer",runtime_consumer=mode=="consumer")),
            references=dict(pipeline=dict(id=DEFINITION)))),version=3)
        run=value.get("data",{}).get("id")
        require(code==201 and uuid(run),"native_request_ambiguous_no_retry")
        receipt.update(status="submitted",run_id=run);save();print(json.dumps(receipt),flush=True)
        deadline=time.monotonic()+2400
        while time.monotonic()<deadline:
            try:
                _,value=api(token,"/runs/"+run,version=3)
                attrs=validate_run(value,source,DEFINITION)
            except ValueError as error:
                if str(error).startswith("circleci_http_404_"):
                    time.sleep(15);continue
                raise
            if attrs.get("phase")=="ended" and attrs.get("current_outcome")=="succeeded":
                _,value=api(token,"/pipeline/"+run+"/workflow")
                workflows=value.get("items",[])
                require(len(workflows)==1 and workflows[0].get("name")=="arm64-archive-validation","native_workflow_identity")
                workflow=workflows[0]["id"];_,value=api(token,"/workflow/"+workflow+"/job")
                jobs=value.get("items",[])
                require(len(jobs)==1 and jobs[0].get("name")=="arm64-ios-archive" and jobs[0].get("status")=="success",
                    "native_job_not_successful")
                receipt.update(status="success",workflow_id=workflow,job_number=jobs[0]["job_number"],
                    worker_job_id=jobs[0]["id"]);save();print(json.dumps(receipt),flush=True);return 0
            time.sleep(15)
        raise ValueError("native_request_pending_no_retry")
    except Exception as error:
        receipt["status"]="unconfirmed_no_retry";save()
        code=str(error) if type(error) is ValueError and re.fullmatch(r"[a-z0-9_]+",str(error)) else "native_request_failed"
        print(code,file=sys.stderr);return 1
if __name__=="__main__":raise SystemExit(main())
