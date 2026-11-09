"""Closed offline invitation evidence; never publish raw invitation/account/catalog data."""
import json
import os
from pathlib import Path
import tempfile

FIELDS={"app","apps","name","appName","bundleId","bundleIdentifier","appAdamId","adamId","appId",
    "builds","build","buildId","buildID","latestBuild","version","platform","status","state",
    "invitation","invitationState","invitationStatus","tester","testerId","invitationId","token",
    "accepted","isAccepted","canAccept","canInstall","isAvailable","isExpired","isFull","isRemoved",
    "publicLinkId","inviteCode","betaReviewStatus","devices","expirationDate","data","message","messages",
    "isTester","isUserInvited","isInvited","code","reason","isBetaAgreementAccepted","requiresAgreement",
    "termsAccepted","hasAcceptedTerms","id","isCompatible","hasFullSlots","appAdamID","bundleID"}
FLAGS={"accepted","isAccepted","canAccept","canInstall","isAvailable","isExpired","isFull","isRemoved",
    "isTester","isUserInvited","isInvited","isBetaAgreementAccepted","requiresAgreement","termsAccepted",
    "hasAcceptedTerms","isCompatible","hasFullSlots"}
STATES={"ACCEPTED","INVITED","PENDING","AVAILABLE","FULL","EXPIRED","REMOVED","NOT_AVAILABLE",
    "ELIGIBLE","INELIGIBLE","ACTIVE","INACTIVE","NOT_JOINED","JOINED","OPEN","CLOSED"}
IDS={"bundleId","bundleIdentifier","bundleID","appAdamId","appAdamID","adamId","appId"}

def walk(value):
    queue=[("root",value)];count=0
    while queue:
        path,item=queue.pop(0);count+=1
        if count>4096:raise ValueError()
        if type(item) is dict:
            yield path,item
            queue.extend((path+"."+key,child) for key,child in item.items() if key in FIELDS and type(child) in (dict,list))
        elif type(item) is list:
            queue.extend((path+"[]",child) for child in item[:256] if type(child) in (dict,list))

def summarize(invitation,catalog):
    result={"schema":"tf-invitation-summary-v1","target_name_matches":False,"fields":[],
        "states":[],"platforms":[],"flags":{},"objects":[],"catalog_app_binding_match":False,
        "acceptance_attempted":False,"network_requests":0}
    present=set();states=set();platforms=set();flags={};ids=set()
    for path,item in walk(invitation):
        present.update(set(item)&FIELDS)
        if len(result["objects"])<16:result["objects"].append({"path":path[:256],"fields":sorted(set(item)&FIELDS),"other_field_count":min(256,len(set(item)-FIELDS))})
        for key,value in item.items():
            if key in ("name","appName") and type(value) is str and value in {"A.I.","A.I. beta"}:result["target_name_matches"]=True
            if key in ("status","state","invitationState","invitationStatus") and type(value) is str:
                states.add(value.upper() if value.upper() in STATES else "OTHER")
            if key=="platform" and type(value) is str:platforms.add(value.lower() if value.lower() in {"ios","iphoneos","macos","osx","tvos","visionos"} else "other")
            if key in FLAGS and type(value) is bool:flags.setdefault(key,set()).add(value)
            if key in IDS and type(value) in (str,int):ids.add((key,str(value)))
    match=False
    for _,item in walk(catalog):
        if any((key,str(value)) in ids for key,value in item.items() if key in IDS and type(value) in (str,int)):match=True
    result.update(fields=sorted(present),states=sorted(states),platforms=sorted(platforms),
        flags={key:sorted(values) for key,values in sorted(flags.items())},catalog_app_binding_match=match)
    return result

def main():
    os.umask(0o077);env=dict(os.environ)
    receipt={"schema":"tf-invitation-probe-v1","status":"inspection_failed",
        "run_id":env.get("GITHUB_RUN_ID"),"source_commit":env.get("GITHUB_SHA")}
    try:
        if env.get("GITHUB_ACTIONS")!="true":raise ValueError()
        from tf_virtual_restore import restore
        with tempfile.TemporaryDirectory(prefix="tf-invite-offline-",dir=env["RUNNER_TEMP"]) as folder:
            root=Path(folder);root.chmod(0o700);restore(root,env)
            if any((root/name).stat().st_size>16*1024*1024 for name in ("invitation.json","catalog.json")):raise ValueError()
            receipt["result"]=summarize(json.loads((root/"invitation.json").read_bytes()),json.loads((root/"catalog.json").read_bytes()))
            receipt["status"]="inspection_verified"
    except Exception:
        pass
    Path("tf-invitation-inspection.json").write_text(json.dumps(receipt,sort_keys=True))
    print(json.dumps(receipt,sort_keys=True),flush=True)
    return 0 if receipt["status"]=="inspection_verified" else 2
if __name__=="__main__":raise SystemExit(main())
