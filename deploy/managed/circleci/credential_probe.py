"""CircleCI-only synthetic lease probe. Private key and plaintext never leave a temporary directory."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from credential_envelope import context, consumer, open_envelope, public_env, require

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

def call(origin,path,value):
    require(re.fullmatch(r"https://ipazake-free-control-pilot\.[a-z0-9][a-z0-9-]{0,62}\.workers\.dev",origin)
            and path in ("/v1/runtime/lease-request","/v1/runtime/lease-read"),"lease_probe_origin")
    token=os.environ.get("CIRCLE_OIDC_TOKEN_V3","")
    require(token and len(token)<=16384,"lease_probe_identity")
    request=urllib.request.Request(origin+path,data=json.dumps(value).encode(),method="POST",
        headers={"X-Ipazake-Job-Token":token,"Content-Type":"application/json",
                 "User-Agent":"ipa-decrypt-circleci-runtime/0.2"})
    with urllib.request.build_opener(NoRedirect).open(request,timeout=20) as response:
        require(response.status==200,"lease_probe_response")
        raw=response.read(360001);require(len(raw)<=360000,"lease_probe_response_limit")
    value=json.loads(raw);require(value.get("ok") is True,"lease_probe_pending")
    return value

def main():
    task=json.loads(sys.stdin.buffer.read(4097))
    origin=os.environ.get("PROBE_CONTROL_URL","")
    with tempfile.TemporaryDirectory(prefix="ipazake-lease-") as folder:
        key=Path(folder)/"identity.txt"
        subprocess.run(["age-keygen","-o",str(key)],check=True,capture_output=True,
                       timeout=15,env=public_env(os.environ))
        recipient=subprocess.check_output(["age-keygen","-y",str(key)],text=True,
                       timeout=15,env=public_env(os.environ)).strip()
        expected=context(dict(schema="circleci-credential-request-v1",job_id=task["job_id"],
            run_id=task["run_id"],worker_job_id=task["worker_job_id"],source_sha=task["source_sha"],
            recipient=recipient,nonce=secrets.token_hex(16),expires_at=int(time.time())+240,profile="synthetic"))
        consumer(os.environ,expected)
        identity=dict(job_id=expected["job_id"],worker_job_id=expected["worker_job_id"])
        answer=call(origin,"/v1/runtime/lease-request",dict(identity,recipient=recipient,
                    nonce=expected["nonce"],expires_at=expected["expires_at"]))
        require(answer.get("context")==expected,"lease_probe_request_binding")
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            answer=call(origin,"/v1/runtime/lease-read",identity)
            if answer.get("ciphertext"):
                require(answer.get("context")==expected,"lease_probe_read_binding")
                cipher=base64.b64decode(answer["ciphertext"],validate=True)
                digest=hashlib.sha256(cipher).hexdigest()
                require(digest==answer.get("cipher_sha256"),"lease_probe_cipher_digest")
                values=open_envelope(cipher,key,expected)
                require(values==dict(fixture="synthetic-private-fixture"),"lease_probe_plaintext")
                print(json.dumps(dict(schema="circleci-credential-probe-v1",verified=True,
                    job_id=task["job_id"],source_commit=task["source_sha"],cipher_sha256=digest,
                    production=False,apple_credentials=False)),flush=True)
                return
            time.sleep(3)
        raise ValueError("lease_probe_timed_out")

if __name__=="__main__":
    try:
        main()
    except Exception:
        print("circleci_credential_probe_failed",file=sys.stderr)
        sys.exit(1)
