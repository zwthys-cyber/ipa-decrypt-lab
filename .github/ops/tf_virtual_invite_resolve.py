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
                if (root/"accept-response.json").is_file():
                    receipt["accept_response_inspection"]=summarize(json.loads((root/"accept-response.json").read_bytes()),[])
                nodes=list(objects(catalog))
                fields={"apps","appId","appAdamId","bundleId","bundleIdentifier","id","data","platform","platforms","ios","macos","availableApps","unavailableApps"}
                receipt["catalog_shape"]={"root_kind":"object" if type(catalog) is dict else "array" if type(catalog) is list else "other",
                    "root_fields":sorted(set(catalog)&fields) if type(catalog) is dict else [],
                    "app_id_nodes":sum(1 for item in nodes if "appId" in item),
                    "bundle_nodes":sum(1 for item in nodes if "bundleId" in item or "bundleIdentifier" in item),
                    "object_count":min(20000,len(nodes)),
                    "fields_present":sorted(set().union(*(set(item)&fields for item in nodes)) if nodes else set())}
                found=predicates(catalog,bundle,identifier);receipt["binding_predicates"]=found
                code,details=native("--invite-bind",root,env);receipt["details_result"]=details
                receipt["invitation_accepted"]=code==0 and details["status"]=="invitation_binding_verified"
                receipt["status"]="membership_verified" if receipt["invitation_accepted"] else "membership_not_verified"
            finally:seal(root,env,receipt)
    except Exception:pass
    Path("tf-accept-receipt.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="membership_verified" else 2
if __name__=="__main__":raise SystemExit(main())
