"""Publish only a source-bound proof of the no-send generic worker export."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile
from tf_task_contract import fingerprint
from tf_task_runtime import GitHub
RID="tf_eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
def need(value):
    if not value:raise ValueError("tf_export_proof_invalid")
def main():
    api=GitHub(os.environ["GH_TOKEN"]);run=os.environ["GITHUB_RUN_ID"];source=os.environ["GITHUB_SHA"];stamp=fingerprint()
    items=api.call("/actions/runs/"+run+"/artifacts?per_page=100")["artifacts"]
    found=[item for item in items if item.get("name")=="tf-result-"+RID and item.get("expired") is False]
    need(len(found)==1);item=found[0];need(0<item.get("size_in_bytes",0)<=65536)
    with tempfile.TemporaryDirectory() as folder:
        path=Path(folder)/"result.zip";api.archive(item["id"],path,max_bytes=65536)
        need("sha256:"+hashlib.sha256(path.read_bytes()).hexdigest()==item.get("digest"))
        with zipfile.ZipFile(path) as archive:
            need(archive.namelist()==["tf-worker-result.json"] and archive.getinfo("tf-worker-result.json").file_size<=16384)
            result=json.loads(archive.read("tf-worker-result.json"))
    need(result.get("schema")=="tf-worker-result-v1" and result.get("request_id")==RID and result.get("run_id")==run
        and result.get("source_commit")==source and result.get("worker_fingerprint")==stamp
        and result.get("status")=="encrypted_artifact_ready" and result.get("decryption_proven") is True
        and result.get("invitation_accepted") is True and result.get("acceptance_attempted") is False
        and result.get("delivered") is False and result.get("new_authorization") is False
        and type(result.get("decrypted_pages")) is int and result["decrypted_pages"]>0)
    value={"schema":"tf-export-contract-proof-v1","worker_fingerprint":stamp,"run_id":run,"source_commit":source,
        "plaintext_verified":True,"new_acceptance":False,"new_authorization":False,"file_sent":False}
    Path("tf-export-proof.json").write_text(json.dumps(value,sort_keys=True))
    with Path(os.environ["GITHUB_OUTPUT"]).open("a") as output:output.write("artifact=tf-export-proof-"+stamp+"\n")
    print(json.dumps(value,sort_keys=True),flush=True)
if __name__=="__main__":main()
