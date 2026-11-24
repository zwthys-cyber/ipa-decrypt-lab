"""Explicit operator cleanup of one expired, uploader-owned private file.

Default is inspection only. Permanent deletion is never scheduled or performed by CI.
"""
import argparse
import os
from pathlib import Path
import re
import sys
from private_upload import Drive,Journal,Stop,need,encode,decode,endpoint,request,GOOGLE,FILE,ISSUER,JOB,MAX

def inspect(drive,state,job):
    need(state and state.get("stage") in {"registered","retired"} and state.get("job_id")==job and
         state.get("owner")==drive.email.lower(),"cleanup_journal_not_eligible")
    record=state.get("record")
    need(type(record) is dict and set(record)=={"filename","bytes","sha256"} and
         type(record["bytes"]) is int and 0<record["bytes"]<=MAX and
         type(record["sha256"]) is str and re.fullmatch("[a-f0-9]{64}",record["sha256"]),"cleanup_record_invalid")
    file_id=state.get("file_id")
    need(isinstance(file_id,str) and FILE.fullmatch(file_id),"cleanup_record_invalid")
    receipt=drive.verify(record,file_id)
    f=drive.get("files/"+file_id+"?fields=id,appProperties,capabilities(canDelete),ownedByMe,trashed")
    need(f.get("id")==file_id and f.get("ownedByMe") is True and f.get("trashed") is False and
         f.get("capabilities",{}).get("canDelete") is True and
         f.get("appProperties",{}).get("pilot_job")==job and
         f.get("appProperties",{}).get("pilot_schema")=="private-link-v1","cleanup_origin_unverified")
    return {**receipt,"job_id":job}

def cleanup(drive,journal,job,origin,token,confirm=False,send=request):
    state=journal.read()
    if state and state.get("stage")=="deleted":
        need(state.get("job_id")==job and state.get("owner")==drive.email.lower(),"cleanup_journal_not_eligible")
        return "private_file_deleted"
    if state and state.get("stage")=="delete_intent":
        raise Stop("deletion_outcome_unknown_do_not_repeat")
    receipt=inspect(drive,state,job)
    if not confirm:return "cleanup_inspection_only"
    p=endpoint(origin)
    need(re.fullmatch(r"https://[A-Za-z0-9.-]{1,253}(?::443)?/?",origin) and p.path in ("","/") and not p.query and
         state.get("registration_origin")==origin.rstrip("/") and isinstance(token,str) and ISSUER.fullmatch(token),
         "cleanup_issuer_mismatch")
    # Safe to repeat an exact retirement, which is idempotent and has no Drive write.
    status,_,data=send("POST",origin.rstrip("/")+"/v1/link-retire",{"Authorization":"Bearer "+token,
        "Content-Type":"application/json"},encode(receipt))
    need(status==200 and decode(data).get("ok") is True,"retirement_not_confirmed")
    state={**state,"stage":"retired"};journal.write(state)
    inspect(drive,state,job)
    journal.write({**state,"stage":"delete_intent"})
    status,_,data=drive.call("DELETE",GOOGLE+"/drive/v3/files/"+receipt["file_id"])
    need((status==204 and not data) or (status==200 and decode(data)=={}),"deletion_outcome_unknown_do_not_repeat")
    journal.write({**state,"stage":"deleted"})
    return "private_file_deleted"

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job",required=True)
    parser.add_argument("--journal",required=True,type=Path)
    parser.add_argument("--confirm-free-account",action="store_true")
    parser.add_argument("--confirm-permanent-delete",action="store_true")
    args=parser.parse_args()
    os.umask(0o077)
    try:
        need(os.environ.get("GITHUB_ACTIONS")!="true" and args.confirm_free_account,"operator_confirmation_required")
        drive=Drive(os.environ.get("PILOT_DRIVE_ACCESS_TOKEN",""),os.environ.get("PILOT_DRIVE_RECIPIENT_EMAIL",""))
        with Journal(args.journal,args.job) as journal:
            result=cleanup(drive,journal,args.job,os.environ.get("PILOT_LINK_ORIGIN",""),
                os.environ.get("PILOT_LINK_ISSUER_TOKEN",""),args.confirm_permanent_delete)
        print(result);return 0
    except Stop as exc:print(str(exc),file=sys.stderr);return 2
    except Exception:print("private_cleanup_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
