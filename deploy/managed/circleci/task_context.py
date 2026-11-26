"""Exact task identity for CircleCI export adapters, separate from GitHub-only workers."""
import os
import platform
import re
import time
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"tools"))
from version_request import selector
from credential_envelope import BRANCH, UUID
RECIPIENT="age1cp0tv9wcxjqpvcmwt6eh6yqxqg25a2msnelc3mxlj9xqcu6fz4cqekfq5d"
FIELDS={"schema","job_id","request_id","run_id","worker_job_id","source_sha","profile","target","version","recipient","deadline"}
def require(ok,code):
    if not ok:
        raise ValueError(code)
def validate(value,env=None,now=None,host=None):
    env=os.environ if env is None else env
    now=int(time.time()) if now is None else now
    host=(platform.system(),platform.machine()) if host is None else host
    require(type(value) is dict and set(value)==FIELDS and value["schema"]=="circleci-export-request-v1","task_schema")
    profile=value.get("profile")
    require(profile in ("default","cn","tf"),"task_profile")
    prefix={"default":"","cn":"cn_","tf":"tf_"}[profile]
    for key,pattern in (("job_id",r"pilot_[a-f0-9]{32}"),("request_id",prefix+r"[a-f0-9]{32}"),
        ("run_id",UUID),("worker_job_id",UUID),("source_sha",r"[a-f0-9]{40}")):
        require(type(value.get(key)) is str and re.fullmatch(pattern,value[key]),"task_identity")
    target=r"[A-Za-z0-9_-]{6,80}" if profile=="tf" else r"[1-9][0-9]{4,19}"
    require(type(value["target"]) is str and re.fullmatch(target,value["target"]),"task_target")
    require(selector(value["version"])==value["version"] and (profile!="tf" or not value["version"]),"task_version")
    require(value["recipient"]==RECIPIENT and type(value["deadline"]) is int and
        now<value["deadline"]<=now+3600,"task_deadline_or_recipient")
    require(env.get("CIRCLECI")=="true" and not env.get("GITHUB_ACTIONS") and
        env.get("CIRCLE_PROJECT_USERNAME")=="zwthys-cyber" and env.get("CIRCLE_PROJECT_REPONAME")=="ipa-decrypt-lab" and
        env.get("CIRCLE_BRANCH")==BRANCH and env.get("CIRCLE_SHA1")==value["source_sha"] and
        env.get("CIRCLE_WORKFLOW_JOB_ID")==value["worker_job_id"] and
        (env.get("RUNTIME_RUN_ID") or env.get("PROBE_PIPELINE"))==value["run_id"],"task_circleci_context")
    require(host==("Darwin","arm64"),"task_arm_macos_required")
    return dict(value)

def credentials(profile,values):
    from credential_envelope import credentials as checked
    return checked(profile,values)

def minimal_env(env,home):
    result={k:env[k] for k in ("PATH","LANG") if k in env}
    result.update(HOME=str(home),TMPDIR=str(home),TMP=str(home),TEMP=str(home))
    return result
