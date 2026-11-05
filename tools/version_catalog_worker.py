"""GitHub-only historical metadata query. Never export native account logs."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from app_preflight import check_app
from version_request import external_id
from native_store import run, classify, classify_download, DOWNLOAD_STAGES

def parse_rows(output):
    totals=re.findall(r"^IPA_LAB_CATALOG_TOTAL:([0-9]{1,5})$",output,re.M)
    rows=re.findall(r"^IPA_LAB_CATALOG_ITEM:([1-9][0-9]{5,19}):([0-9]{1,5}(?:\.[0-9]{1,5}){0,4}):([0-9]{4}-[0-9]{2}-[0-9]{2})$",output,re.M)
    if len(totals)!=1 or not 0<len(rows)<=60 or not len(rows)<=int(totals[0])<=10000:
        raise ValueError("catalog_unavailable")
    if len({r[0] for r in rows})!=len(rows):
        raise ValueError("catalog_invalid")
    return int(totals[0]),[dict(id=i,version=v,date=d) for i,v,d in rows]

def parse_page(output, before=""):
    totals=re.findall(r"^IPA_LAB_CATALOG_TOTAL:([0-9]{1,5})$",output,re.M)
    matches=re.findall(r"^IPA_LAB_CATALOG_NEXT:(end|[1-9][0-9]{5,19})$",output,re.M)
    rows=re.findall(r"^IPA_LAB_CATALOG_ITEM:([1-9][0-9]{5,19}):([0-9]{1,5}(?:\.[0-9]{1,5}){0,4}):([0-9]{4}-[0-9]{2}-[0-9]{2})$",output,re.M)
    if (len(totals)!=1 or len(matches)!=1 or not 0<=len(rows)<=10
            or not len(rows)<=int(totals[0])<=10000 or len({r[0] for r in rows})!=len(rows)):
        raise ValueError("catalog_invalid")
    next_before="" if matches[0]=="end" else matches[0]
    if ((before and (not external_id(before) or any(int(r[0])>=int(before) for r in rows)))
            or (next_before and before and int(next_before)>=int(before))
            or any(next_before and int(r[0])<int(next_before) for r in rows)
            or [int(r[0]) for r in rows]!=sorted((int(r[0]) for r in rows),reverse=True)):
        raise ValueError("catalog_invalid")
    if not rows and not next_before and not before:
        raise ValueError("catalog_unavailable")
    return int(totals[0]),[dict(id=i,version=v,date=d) for i,v,d in rows],next_before

def main():
    os.umask(0o077)
    stage="input"
    try:
        if os.environ.get("GITHUB_ACTIONS")!="true":
            raise ValueError("requires_github_actions")
        rid=os.environ.get("CATALOG_REQUEST_ID","")
        app=os.environ.get("CATALOG_APP_ID","")
        paged=os.environ.get("CATALOG_PAGED")=="1"
        before=os.environ.get("CATALOG_BEFORE","")
        if before and (not paged or not external_id(before)):
            raise ValueError("invalid_request")
        if not re.fullmatch(r"[a-f0-9]{32}",rid):
            raise ValueError("invalid_request")
        stage="metadata"
        info=check_app(app,historical=True)
        email=os.environ["APPLE_ID"].strip()
        env={k:os.environ[k] for k in ("HOME","PATH","LANG","LAB_KBSYNC_HELPER") if k in os.environ}
        env.update(APPLEPACKAGE_PASSWORD=os.environ["APPLE_PASSWORD"],LAB_VERSION_CATALOG="1",LAB_CATALOG_BEFORE=before,LAB_CATALOG_PAGED="1" if paged else "0")
        binary=str(Path(sys.argv[1]).resolve())
        try:
            stage="authenticating"
            result=run(binary,["login",email],env)
            if classify(result)!="authenticated":
                raise ValueError("catalog_authentication_failed")
            with tempfile.TemporaryDirectory(prefix="catalog-private-") as directory:
                stage="catalog_query"
                result=run(binary,["download",email,info["bundleId"],"--output",str(Path(directory)/"unused.ipa")],env,timeout=300)
                markers=re.findall(r"^IPA_LAB_STAGE:([a-z_]+)$",result.stdout or "",re.M)
                last_stage=next((s for s in reversed(markers) if s in DOWNLOAD_STAGES),"unknown")
                print(json.dumps({"status":"catalog_native_result","returncode":result.returncode,
                                  "last_stage":last_stage,
                                  "classification":classify_download(result) if result.returncode else "completed",
                                  "total_markers":len(re.findall(r"^IPA_LAB_CATALOG_TOTAL:",result.stdout or "",re.M)),
                                  "item_markers":len(re.findall(r"^IPA_LAB_CATALOG_ITEM:",result.stdout or "",re.M)),
                                  "bag_fetches":len(re.findall(r"^IPA_LAB_BAG:fetch$",result.stdout or "",re.M)),
                                  "lookup_pools":len(re.findall(r"^IPA_LAB_LOOKUP_POOL:created$",result.stdout or "",re.M)),
                                  "signing_requests":len(re.findall(r"^IPA_LAB_STAGE:generate_kbsync$",result.stdout or "",re.M))}))
                if result.returncode!=0 or list(Path(directory).glob("*.ipa")):
                    raise ValueError("catalog_query_failed")
                stage="catalog_parse"
                if paged:
                    total,rows,next_before=parse_page(result.stdout or "",before)
                else:
                    total,rows=parse_rows(result.stdout or "")
                    next_before=""
        finally:
            try: run(binary,["logout",email],env)
            except Exception: pass
        payload={"schema":"ipa-version-catalog-v2" if paged else "ipa-version-catalog-v1","request_id":rid,"app_id":app,
                 "run_id":os.environ["GITHUB_RUN_ID"],"source_commit":os.environ["GITHUB_SHA"],
                 "total":total,"rows":rows,"before":before,"next_before":next_before}
        Path("catalog-out").mkdir(mode=0o700)
        Path("catalog-out/versions.json").write_text(json.dumps(payload))
        print(json.dumps({"status":"version_catalog_ready","count":len(rows),"total":total}))
        return 0
    except Exception as exc:
        known={"requires_github_actions","invalid_request","catalog_authentication_failed",
               "catalog_query_failed","catalog_unavailable","catalog_invalid"}
        code=str(exc) if isinstance(exc,ValueError) and str(exc) in known else "version_catalog_unavailable"
        print(json.dumps({"status":code,"stage":stage}))
        return 2

if __name__=="__main__":
    raise SystemExit(main())
