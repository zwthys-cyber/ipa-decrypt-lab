"""GitHub-only durable copy of one already-authenticated encrypted canary snapshot."""
import base64
import hashlib
import json
import os
from pathlib import Path
import sys
REPO="zwthys-cyber/ipa-decrypt-lab"
BRANCH="upgrade/managed-runtime-v0.2"
RUN=45866115288
ARTIFACT=15139574335
SOURCE="f3451dd2ba31ac9d9524da4ed7b6ad8f22c1346a"
DIGEST="28654b814e6f38c7dddd0fdb79d5d2202aa8915c23db840c9792e6c2ed4b16dd"
PREFIX="CIRCLECI_CANARY_45866115288_"
CHUNK=30000

def need(value):
    if not value:raise ValueError("cipher_archive_retention_failed")

def validate(raw,metadata):
    need(type(raw) is bytes and raw.startswith(b"age-encryption.org/v1\n") and
        0<len(raw)<=CHUNK*20 and hashlib.sha256(raw).hexdigest()==DIGEST)
    run=metadata.get("workflow_run",{})
    need(metadata.get("id")==ARTIFACT and metadata.get("name")=="circleci-owner-canary-"+str(RUN) and
        metadata.get("expired") is False and run.get("id")==RUN and run.get("head_sha")==SOURCE and
        run.get("repository_id")==1444792484 and run.get("head_repository_id")==1444792484 and
        run.get("head_branch")==BRANCH)
    return raw

def manifest(raw):
    return dict(schema="circleci-retained-canary-v1",source_run=RUN,artifact_id=ARTIFACT,source_sha=SOURCE,
        archive_sha256=DIGEST,archive_bytes=len(raw),
        chunks=[PREFIX+str(i+1).zfill(2) for i in range((len(raw)+CHUNK-1)//CHUNK)],
        permanent_handoff=False,source_restored_after_canary=True)

def assemble(index,env):
    need(type(index) is dict and type(index.get("archive_bytes")) is int and 0<index["archive_bytes"]<=CHUNK*20)
    count=(index["archive_bytes"]+CHUNK-1)//CHUNK
    names=[PREFIX+str(i+1).zfill(2) for i in range(count)]
    need(index.get("chunks")==names)
    parts=[]
    for i,name in enumerate(names):
        text=env.get(name,"")
        need(type(text) is str and 0<len(text)<=40000)
        raw=base64.b64decode(text,validate=True)
        need(len(raw)==min(CHUNK,index["archive_bytes"]-i*CHUNK))
        parts.append(raw)
    raw=b"".join(parts)
    need(raw.startswith(b"age-encryption.org/v1\n") and hashlib.sha256(raw).hexdigest()==DIGEST and index==manifest(raw))
    return raw

def main():
    try:
        env=os.environ
        need(env.get("GITHUB_ACTIONS")=="true" and env.get("GITHUB_REPOSITORY")==REPO and
            env.get("GITHUB_REF")=="refs/heads/"+BRANCH and env.get("GITHUB_RUN_ATTEMPT")=="1" and
            env.get("GITHUB_ACTOR_ID")=="246379322")
        need(sys.argv[1:]==["verify"])
        index=json.loads(env[PREFIX+"INDEX"]);raw=assemble(index,env)
        proof=dict(schema="circleci-canary-retention-v1",mode="verify",encrypted_copy_written=True,
            source_run=RUN,archive_sha256=DIGEST,archive_bytes=len(raw),chunks=len(index["chunks"]),
            readback_verified=True,permanent_handoff=False,apple_operation=False)
        Path("canary-retention-proof.json").write_text(json.dumps(proof,sort_keys=True)+"\n")
        print(json.dumps(proof,sort_keys=True));return 0
    except Exception:
        print("cipher_archive_retention_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
