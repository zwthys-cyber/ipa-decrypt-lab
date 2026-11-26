"""GitHub-only task credential publisher. Uses signed workflow identity, never shared admin tokens."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from credential_envelope import BRANCH,REPO,context,seal,PROFILES
from read_preserved import saved_session
ORIGIN="https://ipazake-free-control-pilot.hahayesadd.workers.dev"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
def need(ok,code="credential_publisher_failed"):
    if not ok:raise ValueError(code)
def identity_token(env):
    parsed=urllib.parse.urlsplit(env.get("ACTIONS_ID_TOKEN_REQUEST_URL",""))
    need(parsed.scheme=="https" and parsed.hostname and parsed.hostname.endswith(".actions.githubusercontent.com") and
        not parsed.username and not parsed.password and parsed.port in (None,443) and not parsed.fragment,"publisher_oidc_endpoint")
    query=urllib.parse.parse_qs(parsed.query,keep_blank_values=True);query["audience"]=[ORIGIN]
    url=urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query,doseq=True)))
    request=urllib.request.Request(url,headers={"Authorization":"Bearer "+env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"],
        "User-Agent":"ipa-decrypt-publisher/0.2"})
    with urllib.request.build_opener(NoRedirect).open(request,timeout=15) as response:
        need(response.status==200);raw=response.read(32769);need(len(raw)<=32768)
    token=json.loads(raw).get("value")
    need(type(token) is str and 0<len(token)<=16384,"publisher_oidc_response")
    return token
def call(path,value,token):
    need(path in ("/v2/runtime/publisher/pending","/v2/runtime/publisher/publish"))
    request=urllib.request.Request(ORIGIN+path,data=json.dumps(dict(value,_source=os.environ["GITHUB_SHA"]),separators=(",",":")).encode(),method="POST",
        headers={"X-Ipazake-Github-Token":token,"X-Ipazake-Source-Sha":os.environ["GITHUB_SHA"],"Content-Type":"application/json",
            "User-Agent":"ipa-decrypt-publisher/0.2"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:
            need(response.status==200);raw=response.read(360001);need(len(raw)<=360000)
    except urllib.error.HTTPError as error:
        code="publisher_http_"+str(error.code)
        try:
            detail=json.loads(error.read(4096)).get("code","")
            if re.fullmatch(r"[a-z_]{1,60}",detail):code+="_"+detail
        except Exception:pass
        raise ValueError(code) from None
    value=json.loads(raw);need(type(value) is dict and value.get("ok") is True);return value
def values(profile,env):
    need(profile in PROFILES,"publisher_profile")
    if profile=="synthetic":return dict(fixture="synthetic-private-fixture")
    if profile=="tf":
        pins=json.loads(Path(__file__).with_name("source-state-pins.json").read_text())
        raw=saved_session(pins,env)
        return dict(TF_SAVED_SESSION_B64=base64.b64encode(raw).decode(),FAIRPLAY_CN_MODEL_B64=env["FAIRPLAY_CN_MODEL_B64"])
    return {key:env[key] for key in PROFILES[profile]}
def main():
    stage="context"
    try:
        env=os.environ
        need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==REPO and
            env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_RUN_ATTEMPT")=="1","publisher_context")
        job=env.get("PUBLISH_JOB_ID","");profile=env.get("PUBLISH_PROFILE","");source=env.get("PUBLISH_SOURCE","")
        need(re.fullmatch(r"pilot_[a-f0-9]{32}",job) and source==env.get("GITHUB_SHA") and profile in PROFILES,"publisher_input")
        stage="identity";token=identity_token(env)
        binding=dict(job_id=job,publisher_run_id=env["GITHUB_RUN_ID"])
        stage="pending"
        for attempt in range(30):
            try:
                pending=call("/v2/runtime/publisher/pending",binding,token);break
            except ValueError as error:
                if not any(code in str(error) for code in ("runtime_provider_pending","runtime_fields","runtime_source_not_ready","publisher_http_503","publisher_http_404","runtime_job_binding")) or attempt==29:raise
                time.sleep(2)
        expected=context(pending["context"])
        need(expected["job_id"]==job and expected["profile"]==profile and expected["source_sha"]==source,"publisher_task_binding")
        stage="sealing"
        cipher=seal(expected,values(profile,env));digest=hashlib.sha256(cipher).hexdigest()
        stage="publishing"
        published=call("/v2/runtime/publisher/publish",dict(binding,context=expected,
            ciphertext=base64.b64encode(cipher).decode()),token)
        need(published.get("cipher_sha256")==digest,"publisher_cipher_digest")
        receipt=dict(schema="circleci-credential-publisher-v1",job_id=job,source_sha=source,profile=profile,
            cipher_sha256=digest,published=True,apple_operation=False)
        Path("credential-publisher-proof.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
        print(json.dumps(receipt,sort_keys=True));return 0
    except Exception as error:
        code=str(error) if isinstance(error,ValueError) and re.fullmatch(r"[a-z0-9_]{1,100}",str(error)) else "credential_publisher_failed"
        print(json.dumps(dict(schema="credential-publisher-diagnostic-v1",stage=stage,code=code)),file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
