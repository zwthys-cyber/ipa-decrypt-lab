"""Read-only resolution after one recorded acceptance POST; never issues another POST."""
import json
import os
from pathlib import Path
import tempfile
from tf_virtual_invite_accept import native,target,objects,seal
from tf_virtual_invite_inspect import summarize,FIELDS

def predicates(catalog,bundle,identifier):
    result={"bundle_match_nodes":0,"specific_id_combined":0,"generic_id_combined":0,"matching_node_fields":[]}
    for item in objects(catalog):
        name=item.get("bundleId",item.get("bundleIdentifier",item.get("bundleID")))
        if name!=bundle:continue
        result["bundle_match_nodes"]+=1
        result["matching_node_fields"].append(sorted(set(item)&FIELDS))
        known=item.get("appAdamId",item.get("appAdamID",item.get("adamId",item.get("appId"))))
        if type(known) in (str,int) and str(known)==identifier:result["specific_id_combined"]+=1
        if type(item.get("id")) in (str,int) and str(item["id"])==identifier:result["generic_id_combined"]+=1
    result["matching_node_fields"]=result["matching_node_fields"][:8]
    return result

def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-invite-resolution-v1","status":"resolution_failed","run_id":env.get("GITHUB_RUN_ID"),
        "source_commit":env.get("GITHUB_SHA"),"acceptance_attempted":False,"invitation_accepted":False,
        "downloaded":False,"decryption_proven":False}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(prefix="tf-invite-resolve-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700);restore(root,env)
            try:
                code,result=native("--invite-refresh",root,env);receipt["result"]=result
                if code:raise ValueError()
                info,bundle,identifier=target(root)
                catalog=json.loads((root/"catalog.json").read_bytes())
                receipt["inspection"]=summarize(info,catalog)
                found=predicates(catalog,bundle,identifier);receipt["binding_predicates"]=found
                receipt["invitation_accepted"]=found["specific_id_combined"]>0 or found["generic_id_combined"]>0
                receipt["status"]="membership_verified" if receipt["invitation_accepted"] else "membership_not_verified"
            finally:seal(root,env,receipt)
    except Exception:pass
    Path("tf-accept-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="membership_verified" else 2
if __name__=="__main__":raise SystemExit(main())
