"""Bounded CN history verification; public metadata/ciphertext only, never send an IPA."""
import hashlib,json,os,re,sys,tempfile,time,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from telegram_queue import GitHub,validate_receipt
from version_catalog import validate
from version_request import selector,external_id
from native_runtime import fingerprint
CATALOG_RID="cn_99999999999999999999999999999999"
EXPORT_RID="cn_88888888888888888888888888888888"
APP="1661733229"
WORKFLOW=".github/workflows/cn-history-smoke.yml"

def artifact(client,run_id,name,limit):
    found=[a for a in client.call("/actions/runs/"+str(run_id)+"/artifacts?per_page=100").get("artifacts",[])
           if a.get("name")==name and a.get("expired") is False]
    assert len(found)==1 and 0<found[0]["size_in_bytes"]<=limit,"proof_artifact_unavailable"
    item=found[0]
    with tempfile.TemporaryDirectory(prefix="cn-history-proof-") as directory:
        path=Path(directory)/"artifact.zip"
        client.archive(item["id"],path,max_bytes=limit)
        assert item.get("digest")=="sha256:"+hashlib.sha256(path.read_bytes()).hexdigest(),"proof_archive_digest"
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            if name.startswith("versions-"):
                assert names==["versions.json"],"catalog_inventory"
                member="versions.json"
            elif name.startswith("delivery-"):
                assert set(names)=={"receipt.json","package.ipa.age"} and len(names)==2,"delivery_inventory"
                member="receipt.json"
            else:
                assert names==["proof.json"],"proof_inventory"
                member="proof.json"
            assert archive.getinfo(member).file_size<=32768,"proof_metadata_size"
            return json.loads(archive.read(member))

def choose(payload,run,sha):
    validate(payload,CATALOG_RID,APP,run,sha)
    current=payload.get("current_version","")
    assert selector(current) and not external_id(current),"current_version_unavailable"
    def number(value):
        parts=tuple(map(int,value.split(".")))
        return parts+(0,)*(5-len(parts))
    found=[row for row in payload["rows"] if number(row["version"])<number(current)]
    assert found,"older_cn_version_unavailable"
    return found[0]

def main(mode):
    client=GitHub(os.environ["GH_TOKEN"]);sha=os.environ["GITHUB_SHA"];run=os.environ["GITHUB_RUN_ID"]
    if mode=="choose":
        payload=artifact(client,run,"versions-"+CATALOG_RID,131072)
        row=choose(payload,run,sha)
        with open(os.environ["GITHUB_OUTPUT"],"a") as stream:
            stream.write("version_id="+row["id"]+"\nversion="+row["version"]+"\n")
        print(json.dumps({"status":"older_cn_version_selected","catalog_verified":True}))
    elif mode=="record":
        payload=artifact(client,run,"versions-"+CATALOG_RID,131072)
        row=choose(payload,run,sha)
        receipt=artifact(client,run,"delivery-"+EXPORT_RID,256*1024*1024)
        validate_receipt(receipt,EXPORT_RID,run,sha)
        assert receipt.get("requested_version")==row["id"]==receipt.get("external_version_id"),"historical_id_mismatch"
        assert receipt.get("resolved_version")==row["version"],"historical_display_mismatch"
        assert receipt.get("app_id")==APP and receipt.get("encrypted_images",0)>0 and receipt.get("decrypted_pages",0)>0,"missing_plaintext_proof"
        proof={"schema":"cn-history-proof-v1","source_commit":sha,"source_fingerprint":fingerprint(),
            "run_id":run,"app_id":APP,"account_profile":"cn","catalog_verified":True,
            "older_than_current":True,"external_version_id":row["id"],"resolved_version":row["version"],
            "plaintext_verified":True,"delivered":False,"new_authorization":False}
        Path("cn-history-proof").mkdir()
        Path("cn-history-proof/proof.json").write_text(json.dumps(proof)+"\n")
        print(json.dumps({"status":"cn_history_plaintext_verified","delivered":False}))
    elif mode=="gate":
        expected=fingerprint()
        for poll in range(60):
            runs=client.call("/actions/workflows/cn-history-smoke.yml/runs?branch=main&event=workflow_run&per_page=20").get("workflow_runs",[])
            for candidate in runs:
                if (candidate.get("head_sha")==sha and candidate.get("conclusion")=="success"
                        and candidate.get("path")==WORKFLOW and candidate.get("head_branch")=="main"):
                    proof=artifact(client,candidate["id"],"cn-history-proof-"+expected,131072)
                    assert proof.get("schema")=="cn-history-proof-v1" and proof.get("source_commit")==sha
                    assert proof.get("source_fingerprint")==expected and proof.get("run_id")==str(candidate["id"])
                    assert proof.get("account_profile")=="cn" and proof.get("app_id")==APP
                    assert all(proof.get(k) is True for k in ("catalog_verified","older_than_current","plaintext_verified"))
                    assert proof.get("delivered") is False and proof.get("new_authorization") is False
                    print(json.dumps({"status":"cn_history_deployment_ready","proof_run":candidate["id"]}));return
            print(json.dumps({"status":"cn_history_proof_pending","poll":poll+1}),flush=True)
            time.sleep(30)
        raise ValueError("cn_history_proof_timeout")
    else:raise ValueError("invalid_mode")
if __name__=="__main__":main(sys.argv[1])
