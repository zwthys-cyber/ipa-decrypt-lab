"""Operator-run resumable Drive upload for synthetic or rights-cleared private files.

No production worker integration, public sharing, payment API, or automatic re-creation.
Keep a private local journal; never put tokens, session URLs, or receipts in public CI.
"""
import argparse
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import stat
import sys
import tempfile
from urllib.parse import urlsplit

MAX=2_000_000_000
FREE_LIMIT=15*1024**3
RESERVE=1_000_000_000
CHUNK=8*1024**2
GOOGLE="https://www.googleapis.com"
FIELDS="id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey"
JOB=re.compile(r"pilot_[a-f0-9]{32}")
FILE=re.compile(r"[A-Za-z0-9_-]{10,160}")
ACCESS=re.compile(r"[A-Za-z0-9._~-]{20,2048}")
ISSUER=re.compile(r"[A-Za-z0-9_-]{43,128}")
EMAIL=re.compile(r"[^\s@]{1,128}@[^\s@]{1,128}")

class Stop(Exception): pass
def need(value,reason="upload_unverified"):
    if not value:raise Stop(reason)
def encode(value):return json.dumps(value,separators=(",",":"),ensure_ascii=True).encode()
def decode(data):
    value=json.loads(data);need(type(value) is dict);return value
def decimal(value):
    need(isinstance(value,str) and re.fullmatch(r"[0-9]{1,20}",value))
    return int(value)
def endpoint(value):
    p=urlsplit(value)
    need(p.scheme=="https" and p.hostname and not p.username and not p.password and p.port in (None,443) and not p.fragment)
    return p
def request(method,url,headers,body=None):
    p=endpoint(url)
    conn=http.client.HTTPSConnection(p.hostname,443,timeout=60,context=ssl.create_default_context())
    try:
        conn.request(method,(p.path or "/")+("?" + p.query if p.query else ""),body=body,headers=headers)
        response=conn.getresponse()
        data=response.read(32769)
        need(len(data)<=32768,"response_too_large")
        return response.status,{k.lower():v for k,v in response.getheaders()},data
    except (OSError,http.client.HTTPException):
        raise Stop("network_outcome_unknown") from None
    finally:conn.close()
def session_url(url):
    p=endpoint(url)
    need(p.netloc in {"www.googleapis.com","www.googleapis.com:443"} and p.path=="/upload/drive/v3/files" and
         len(p.query)<=4096 and "upload_id=" in p.query and not any(c.isspace() for c in url),"invalid_upload_session")
    return url
def validate_file(stream,name):
    info=os.fstat(stream.fileno())
    need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_mode&0o077==0,"input_not_private")
    need(0<info.st_size<=MAX,"file_size_out_of_bounds")
    need(1<=len(name)<=160 and not name.startswith(".") and
         all(c.isalnum() or c in " ._()-" for c in name) and
         Path(name).suffix.lower() in {".ipa",".zip",".bin",".txt"},"filename_invalid")
    h=hashlib.sha256()
    for data in iter(lambda:stream.read(CHUNK),b""):h.update(data)
    need(os.fstat(stream.fileno()).st_size==info.st_size,"input_changed")
    return {"filename":name,"bytes":info.st_size,"sha256":h.hexdigest()}

def quota(value,email,size):
    need(value.get("user",{}).get("emailAddress","").lower()==email.lower(),"account_mismatch")
    q=value.get("storageQuota",{})
    limit,usage=decimal(q.get("limit")),decimal(q.get("usage"))
    need(0<limit<=FREE_LIMIT and usage<=limit and limit-usage>=size+RESERVE,"free_storage_insufficient")
def ack(status,headers,data,size):
    if status in (200,201):
        value=decode(data);need(isinstance(value.get("id"),str) and FILE.fullmatch(value["id"]))
        return None,value["id"]
    need(status==308,"upload_session_unavailable")
    range_=headers.get("range","")
    if not range_:return 0,None
    found=re.fullmatch(r"bytes=0-([0-9]{1,12})",range_)
    need(found and 0<int(found[1])+1<size,"invalid_upload_offset")
    return int(found[1])+1,None

class Drive:
    def __init__(self,token,email,send=request):
        need(isinstance(token,str) and ACCESS.fullmatch(token) and isinstance(email,str) and EMAIL.fullmatch(email),"invalid_drive_credentials")
        self.email=email
        self.send=send
        self.headers={"Authorization":"Bearer "+token,"Accept":"application/json"}
    def call(self,method,url,body=None,headers=None):
        return self.send(method,url,{**self.headers,**(headers or {})},body)
    def get(self,path):
        status,_,data=self.call("GET",GOOGLE+"/drive/v3/"+path)
        need(status==200,"drive_metadata_unavailable");return decode(data)
    def check_quota(self,size):
        quota(self.get("about?fields=storageQuota(limit,usage),user(emailAddress)"),self.email,size)
    def start(self,record):
        raw=encode({"name":record["filename"],"mimeType":"application/octet-stream"})
        status,headers,_=self.call("POST",GOOGLE+"/upload/drive/v3/files?uploadType=resumable&fields="+FIELDS,raw,
            {"Content-Type":"application/json","X-Upload-Content-Type":"application/octet-stream","X-Upload-Content-Length":str(record["bytes"])})
        need(status==200,"upload_start_unconfirmed")
        return session_url(headers.get("location",""))
    def resume(self,session,size):
        return ack(*self.call("PUT",session_url(session),b"",{"Content-Range":"bytes */"+str(size),"Content-Length":"0"}),size)
    def chunk(self,session,stream,offset,size):
        stream.seek(offset)
        data=stream.read(min(CHUNK,size-offset))
        need(len(data)==min(CHUNK,size-offset),"input_changed")
        end=offset+len(data)
        result=ack(*self.call("PUT",session_url(session),data,{"Content-Type":"application/octet-stream",
            "Content-Range":f"bytes {offset}-{end-1}/{size}","Content-Length":str(len(data))}),size)
        position,file_id=result
        if file_id is None:need(offset<position<=end,"upload_progress_unconfirmed")
        else:need(end==size,"unexpected_upload_completion")
        return result
    def verify(self,record,file_id):
        need(isinstance(file_id,str) and FILE.fullmatch(file_id))
        f=self.get("files/"+file_id+"?fields="+FIELDS)
        need(f.get("id")==file_id and f.get("name")==record["filename"] and f.get("size")==str(record["bytes"]) and
             f.get("sha256Checksum")==record["sha256"] and f.get("trashed") is False and f.get("ownedByMe") is True and
             f.get("mimeType")=="application/octet-stream" and not f.get("resourceKey"),"file_integrity_unverified")
        p=self.get("files/"+file_id+"/permissions?pageSize=100&fields=nextPageToken,permissions(type,role,emailAddress,deleted)")
        permissions=p.get("permissions")
        need(not p.get("nextPageToken") and isinstance(permissions,list) and len(permissions)==1,"file_not_owner_only")
        item=permissions[0]
        need(item.get("type")=="user" and item.get("role")=="owner" and not item.get("deleted") and
             item.get("emailAddress","").lower()==self.email.lower(),"file_not_owner_only")
        return {**record,"file_id":file_id}

class Journal:
    def __init__(self,root,job):
        need(JOB.fullmatch(job),"invalid_job")
        self.root=root
        root.mkdir(mode=0o700,parents=True,exist_ok=True)
        info=root.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and info.st_mode&0o077==0,"journal_not_private")
        self.path=root/(job+".json")
        self.lock_path=root/(job+".lock")
    def __enter__(self):
        fd=os.open(self.lock_path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info=os.fstat(fd)
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_mode&0o077==0)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except Exception:os.close(fd);raise
        self.fd=fd;return self
    def __exit__(self,*_):os.close(self.fd)
    def read(self):
        try:fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:return None
        with os.fdopen(fd,"rb") as stream:
            info=os.fstat(stream.fileno())
            need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and info.st_mode&0o077==0 and info.st_size<=16384)
            return decode(stream.read(16385))
    def write(self,value):
        fd,tmp=tempfile.mkstemp(dir=self.root,prefix=".pending-")
        try:
            with os.fdopen(fd,"wb") as stream:
                stream.write(encode(value));stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,self.path)
            d=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(d)
            finally:os.close(d)
        finally:Path(tmp).unlink(missing_ok=True)

def upload(drive,stream,record,journal,job):
    binding={"job_id":job,"record":record,"owner":drive.email.lower()}
    state=journal.read()
    if state is None:
        drive.check_quota(record["bytes"])
        state={**binding,"stage":"start_intent"}
        journal.write(state)
        state={**state,"stage":"uploading","session":drive.start(record)}
        journal.write(state)
    else:
        need(all(state.get(k)==v for k,v in binding.items()),"journal_binding_mismatch")
    if state.get("stage")=="start_intent":
        raise Stop("upload_creation_unknown_do_not_recreate")
    if state.get("stage")=="uploading":
        size=record["bytes"]
        session=state["session"]
        offset,file_id=drive.resume(session,size)
        while file_id is None:
            need(0<=offset<size)
            offset,file_id=drive.chunk(session,stream,offset,size)
        state={**binding,"stage":"uploaded","file_id":file_id}
        journal.write(state)
    need(state.get("stage") in {"uploaded","registration_intent","registered"},"journal_stage_invalid")
    receipt=drive.verify(record,state["file_id"])
    return {**receipt,"job_id":job},state

def register(receipt,state,journal,origin,token,send=request):
    p=endpoint(origin)
    need(re.fullmatch(r"https://[A-Za-z0-9.-]{1,253}(?::443)?/?",origin) and p.path in ("","/") and not p.query and
         isinstance(token,str) and ISSUER.fullmatch(token),"issuer_configuration_invalid")
    if state.get("stage")=="registered":
        need(state.get("registration_origin")==origin.rstrip("/"),"registration_origin_mismatch")
        return
    need(state.get("stage")=="uploaded","registration_outcome_unknown_check_database")
    state={**state,"stage":"registration_intent","registration_origin":origin.rstrip("/")}
    journal.write(state)
    status,_,data=send("POST",origin.rstrip("/")+"/v1/link-register",{"Authorization":"Bearer "+token,
        "Content-Type":"application/json"},encode(receipt))
    need(status==201 and decode(data).get("ok") is True,"registration_outcome_unknown_check_database")
    journal.write({**state,"stage":"registered"})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file",required=True,type=Path)
    parser.add_argument("--job",required=True)
    parser.add_argument("--journal",required=True,type=Path)
    parser.add_argument("--confirm-free-account",action="store_true")
    parser.add_argument("--confirm-authorized-file",action="store_true")
    parser.add_argument("--register",action="store_true")
    args=parser.parse_args()
    os.umask(0o077)
    try:
        need(args.confirm_free_account and args.confirm_authorized_file,"operator_confirmation_required")
        need(os.environ.get("GITHUB_ACTIONS")!="true","operator_only_no_live_ci_upload")
        drive=Drive(os.environ.get("PILOT_DRIVE_ACCESS_TOKEN",""),os.environ.get("PILOT_DRIVE_RECIPIENT_EMAIL",""))
        fd=os.open(args.file,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,"rb") as stream,Journal(args.journal,args.job) as journal:
            record=validate_file(stream,args.file.name)
            receipt,state=upload(drive,stream,record,journal,args.job)
            if args.register:
                register(receipt,state,journal,os.environ.get("PILOT_LINK_ORIGIN",""),os.environ.get("PILOT_LINK_ISSUER_TOKEN",""))
        print("private_link_registered" if args.register else "private_upload_verified")
        return 0
    except Stop as exc:
        # Stop messages are closed internal codes. No paths, URLs, receipts or account data.
        print(str(exc),file=sys.stderr);return 2
    except Exception:
        print("private_upload_failed",file=sys.stderr);return 2

if __name__=="__main__":raise SystemExit(main())
