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
import time
from urllib.parse import urlsplit, urlencode
from zip_preflight import inspect as inspect_archive, ArchiveError

MAX=10_000_000_000
FREE_LIMIT=15*1024**3
RESERVE=1_000_000_000
CHUNK=8*1024**2
GOOGLE="https://www.googleapis.com"
FIELDS="id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey"
JOB=re.compile(r"pilot_[a-f0-9]{32}")
FILE=re.compile(r"[A-Za-z0-9_-]{10,160}")
ACCESS=re.compile(r"[A-Za-z0-9._~+/=-]{20,2048}")
CLIENT=re.compile(r"[A-Za-z0-9_-]{10,240}\.apps\.googleusercontent\.com")
OPAQUE=re.compile(r"[\x21-\x7e]{12,2048}")
SCOPE="https://www.googleapis.com/auth/drive.file"
OAUTH_URL="https://oauth2.googleapis.com/token"
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
    if Path(name).suffix.lower() in {".zip",".ipa"}:
        try:inspect_archive(stream)
        except ArchiveError:raise Stop("archive_preflight_failed") from None
    stream.seek(0)
    h=hashlib.sha256()
    for data in iter(lambda:stream.read(CHUNK),b""):h.update(data)
    after=os.fstat(stream.fileno())
    need((after.st_size,after.st_mtime_ns,after.st_ctime_ns)==
         (info.st_size,info.st_mtime_ns,info.st_ctime_ns),"input_changed")
    return {"filename":name,"bytes":info.st_size,"sha256":h.hexdigest()}

def quota(value,email,size):
    need(type(size) is int and 0<size<=MAX,"file_size_out_of_bounds")
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

class OAuthSession:
    """Process-local access-token cache; no token persistence or mutation retry."""
    def __init__(self,client_id,client_secret,refresh_token,send=request,clock=time.monotonic):
        need(all(isinstance(v,str) and p.fullmatch(v) for v,p in
                 ((client_id,CLIENT),(client_secret,OPAQUE),(refresh_token,OPAQUE))),"invalid_drive_credentials")
        self._client_id=client_id
        self._secret=client_secret
        self._refresh=refresh_token
        self._send=send
        self._clock=clock
        self._token=None
        self._until=0
        self._blocked=False
    def access(self):
        need(not self._blocked,"drive_reauthorization_required")
        now=self._clock()
        if self._token and now<self._until:return self._token
        self._token=None
        try:
            body=urlencode({"client_id":self._client_id,"client_secret":self._secret,
                            "refresh_token":self._refresh,"grant_type":"refresh_token"}).encode("ascii")
            status,_,raw=self._send("POST",OAUTH_URL,{"Content-Type":"application/x-www-form-urlencoded",
                                    "Accept":"application/json"},body)
            need(len(raw)<=16384,"drive_authorization_unavailable")
            value=decode(raw)
            if status==400 and value.get("error")=="invalid_grant":
                self._blocked=True
                raise Stop("drive_reauthorization_required")
            if value.get("error")=="invalid_client":
                self._blocked=True
                raise Stop("drive_client_configuration_invalid")
            need(status==200,"drive_authorization_unavailable")
            token=value.get("access_token")
            lifetime=value.get("expires_in")
            need(isinstance(token,str) and ACCESS.fullmatch(token) and
                 isinstance(value.get("token_type"),str) and value["token_type"].lower()=="bearer" and
                 type(lifetime) is int and 120<=lifetime<=86400 and
                 isinstance(value.get("scope"),str) and value["scope"].strip()==SCOPE and
                 "refresh_token" not in value,"drive_authorization_unavailable")
            self._until=now+lifetime-60
            need(self._clock()<self._until,"drive_authorization_unavailable")
            self._token=token
            return token
        except Stop:
            raise
        except Exception:
            raise Stop("drive_authorization_unavailable") from None

class Drive:
    def __init__(self,token,email,send=request,*,oauth=None):
        need(isinstance(email,str) and EMAIL.fullmatch(email),"invalid_drive_credentials")
        need((oauth is None and isinstance(token,str) and ACCESS.fullmatch(token)) or
             (isinstance(oauth,OAuthSession) and token is None),"invalid_drive_credentials")
        self.email=email
        self.send=send
        self._token=token
        self._oauth=oauth
    @classmethod
    def from_env(cls,env,send=request,clock=time.monotonic):
        email=env.get("PILOT_DRIVE_RECIPIENT_EMAIL","")
        values=[env.get(k,"") for k in ("PILOT_DRIVE_CLIENT_ID","PILOT_DRIVE_CLIENT_SECRET","PILOT_DRIVE_REFRESH_TOKEN")]
        if any(values):
            # Partial OAuth configuration never silently falls back to a stale manual token.
            return cls(None,email,send,oauth=OAuthSession(*values,send=send,clock=clock))
        return cls(env.get("PILOT_DRIVE_ACCESS_TOKEN",""),email,send)
    def call(self,method,url,body=None,headers=None):
        p=endpoint(url)
        need(p.hostname=="www.googleapis.com" and p.netloc in {"www.googleapis.com","www.googleapis.com:443"} and
             (p.path.startswith("/drive/v3/") or p.path=="/upload/drive/v3/files"),"invalid_drive_endpoint")
        extra=headers or {}
        need(not any(k.lower()=="authorization" for k in extra),"invalid_drive_headers")
        token=self._oauth.access() if self._oauth else self._token
        # Refresh before a provider call; never retry an ambiguous write or a 401 automatically.
        return self.send(method,url,{"Authorization":"Bearer "+token,"Accept":"application/json",**extra},body)
    def get(self,path):
        status,_,data=self.call("GET",GOOGLE+"/drive/v3/"+path)
        need(status==200,"drive_metadata_unavailable");return decode(data)
    def check_quota(self,size):
        quota(self.get("about?fields=storageQuota(limit,usage),user(emailAddress)"),self.email,size)
    def start(self,record,job):
        need(JOB.fullmatch(job),"invalid_job")
        raw=encode({"name":record["filename"],"mimeType":"application/octet-stream",
                    "appProperties":{"pilot_job":job,"pilot_schema":"private-link-v1"}})
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
        state={**state,"stage":"uploading","session":drive.start(record,job)}
        journal.write(state)
    else:
        need(all(state.get(k)==v for k,v in binding.items()),"journal_binding_mismatch")
    if state.get("stage")=="start_intent":
        raise Stop("upload_creation_unknown_do_not_recreate")
    if state.get("stage")=="uploading":
        size=record["bytes"]
        session=state["session"]
        offset,file_id=drive.resume(session,size)
        if file_id is None:
            # Conservatively recheck the full reservation before resuming writes.
            # The provider may not yet count uncommitted chunks in usage.
            drive.check_quota(size)
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
        drive=Drive.from_env(os.environ)
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
