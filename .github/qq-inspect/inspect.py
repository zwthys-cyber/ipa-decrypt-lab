"""Inspect only the specified delivery. No QQ code is executed."""
import hashlib,json,os,plistlib,re,subprocess,tarfile,tempfile,urllib.error,urllib.request,zipfile
from pathlib import Path
RUN=43715591869
ARTIFACT=14162736529
ARCHIVE_SHA="b64c645a1fb1caec309a295c1ab79e7815ee1beb7e95e8fbd1ab4aba997d5e31"
SOURCE="3233fe33090467b29fa986f789e99ca1e25f5bc0"
REQUEST="217b63c6381e1ce3a52cf9c75cac1691"
AGE_URL="https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-darwin-amd64.tar.gz"
AGE_SHA="1d1e4bc66e1427edad7739ae7616157de0e79db8b6d2a1497d7d9925fb06a539"
MAGICS={bytes.fromhex(v) for v in ("cffaedfe","feedfacf","cefaedfe","feedface","cafebabe","bebafeca","cafebabf","bfbafeca")}
HINT=re.compile(r"recall|revoke|OCMsgRecord|KTIKernelMsgListener|onMsgInfoListUpdate|onMsgDelete",re.I)
CLASS=re.compile(r"(?:QQMessageRecallModule|OCMsgRecord|KTIKernelMsgListener|NTAIOFloatEarManager|NTAIOMenuRecallService|.*Recall.*Processor|.*Recall.*Model|.*Recall.*Msg)")
class Rejected(RuntimeError): pass
def require(ok,why):
    if not ok: raise Rejected(why)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None
def download(url,path,limit,headers=None,redirects=0):
    require(url.startswith("https://") and redirects<6,"invalid_download_redirect")
    opener=urllib.request.build_opener(NoRedirect)
    try: response=opener.open(urllib.request.Request(url,headers=headers or {}),timeout=60)
    except urllib.error.HTTPError as e:
        if e.code not in (301,302,303,307,308):
            raise Rejected("download_http_"+str(e.code)) from None
        # Never forward the GitHub bearer token to signed artifact storage.
        return download(e.headers.get("Location",""),path,limit,redirects=redirects+1)
    with response,path.open("xb") as out:
        size=0
        for block in iter(lambda:response.read(1024*1024),b""):
            size+=len(block)
            require(size<=limit,"download_size_limit")
            out.write(block)
def run(args,**kwargs):
    child={k:os.environ[k] for k in ("PATH","HOME","LANG","DEVELOPER_DIR") if k in os.environ}
    p=subprocess.run(args,env=child,stdin=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=300,**kwargs)
    require(p.returncode==0,"native_tool_rejected")
    return p
def metadata(path,work):
    raw=work/"objc.txt"
    with raw.open("wb") as out: run(["xcrun","otool","-arch","all","-ov",str(path)],stdout=out)
    require(raw.stat().st_size<512*1024**2,"metadata_limit")
    records=[]
    current_class=class_indent=last_name=None
    selected=False
    with raw.open(errors="replace") as src:
        for line in src:
            m=re.match(r"^(\s*)(name|types)\s+0x[0-9a-fA-F]+\s+(.*?)\s*$",line)
            if not m: continue
            indentation,field,value=len(m[1]),m[2],m[3]
            if len(value)>1024: continue
            if field=="name":
                if CLASS.fullmatch(value):
                    current_class,class_indent=value,indentation
                    records.append({"class":value})
                elif class_indent is not None and indentation<=class_indent:
                    current_class=class_indent=None
                last_name=value
                selected=bool(current_class or HINT.search(value))
            elif selected and last_name:
                records.append({"class":current_class,"selector":last_name,"types":value})
                selected=False
            require(len(records)<=12000,"candidate_method_limit")
    raw.unlink()
    return records
def main():
    require(os.environ.get("GITHUB_ACTIONS")=="true","actions_only")
    require(os.environ.get("DELIVERY_AGE_IDENTITY","").strip(),"delivery_identity_missing")
    require(os.environ.get("GH_TOKEN",""),"github_token_missing")
    report={"schema":"qq-static-interfaces-v1","source_run":RUN,"runtime_verified":False,"hook_verified":False,"images":[]}
    with tempfile.TemporaryDirectory(prefix="qq-private-") as temp:
        work=Path(temp)
        headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json","User-Agent":"qq-static-inspection"}
        delivery=work/"delivery.zip"
        download(f"https://api.github.com/repos/zwthys-cyber/ipa-decrypt-lab/actions/artifacts/{ARTIFACT}/zip",delivery,400*1024**2,headers)
        require(sha(delivery)==ARCHIVE_SHA,"artifact_digest_mismatch")
        sealed=work/"package.ipa.age"
        with zipfile.ZipFile(delivery) as z:
            require(sorted(z.namelist())==["package.ipa.age","receipt.json"],"unexpected_delivery_members")
            require(z.getinfo("receipt.json").file_size<65536,"receipt_limit")
            receipt=json.loads(z.read("receipt.json"))
            checks={"schema":"ipa-private-delivery-v1","status":"encrypted_artifact_ready","run_id":str(RUN),"source_commit":SOURCE,"request_id":REQUEST,"app_id":"444934666","plaintext_verified":True,"account_data_removed":True,"plaintext_published":False,"resolved_version":"9.3.86"}
            require(all(receipt.get(k)==v for k,v in checks.items()),"receipt_binding_mismatch")
            require(z.getinfo("package.ipa.age").file_size<400*1024**2,"ciphertext_size_limit")
            with z.open("package.ipa.age") as src,sealed.open("xb") as dst:
                for block in iter(lambda:src.read(1024*1024),b""): dst.write(block)
        require(sha(sealed)==receipt["ciphertext_sha256"],"ciphertext_digest_mismatch")
        age_archive=work/"age.tar.gz"
        download(AGE_URL,age_archive,32*1024**2)
        require(sha(age_archive)==AGE_SHA,"age_digest_mismatch")
        age=work/"age"
        with tarfile.open(age_archive) as tar:
            member=tar.getmember("age/age")
            require(member.isfile() and member.size<32*1024**2,"age_binary_invalid")
            with tar.extractfile(member) as src,age.open("xb") as out: out.write(src.read())
        age.chmod(0o700)
        key=work/"identity"
        with os.fdopen(os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),"w") as f:
            f.write(os.environ["DELIVERY_AGE_IDENTITY"].strip()+"\n")
        ipa=work/"qq.ipa"
        try: run([str(age),"--decrypt","-i",str(key),"-o",str(ipa),str(sealed)],stdout=subprocess.PIPE)
        finally: key.unlink(missing_ok=True)
        require(sha(ipa)==receipt["plaintext_sha256"],"plaintext_digest_mismatch")
        require(ipa.stat().st_size==receipt["plaintext_bytes"],"plaintext_size_mismatch")
        report["plaintext_sha256"]=sha(ipa)
        with zipfile.ZipFile(ipa) as z:
            names=z.namelist()
            require(len(names)==len(set(names)),"duplicate_ipa_members")
            require(sum(i.file_size for i in z.infolist())<8*1024**3,"ipa_expansion_limit")
            roots=[n[:-10] for n in names if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist",n)]
            require(len(roots)==1,"app_root_invalid")
            root=roots[0]
            require(z.getinfo(root+"Info.plist").file_size<1024**2,"plist_size_limit")
            info=plistlib.loads(z.read(root+"Info.plist"))
            require(info.get("CFBundleIdentifier")=="com.tencent.mqq","bundle_mismatch")
            require(info.get("CFBundleShortVersionString")=="9.3.86","version_mismatch")
            report["bundle"]={k:info.get(k) for k in ("CFBundleIdentifier","CFBundleShortVersionString","CFBundleVersion","CFBundleExecutable","MinimumOSVersion")}
            main_seen=False
            for entry in z.infolist():
                if entry.is_dir() or not entry.filename.startswith(root): continue
                require(entry.file_size<1536*1024**2,"member_size_limit")
                with z.open(entry) as src:
                    first=src.read(4)
                    if first not in MAGICS: continue
                    binary=work/"image.macho"
                    with binary.open("wb") as out:
                        out.write(first)
                        for block in iter(lambda:src.read(1024*1024),b""): out.write(block)
                load=run(["xcrun","otool","-arch","all","-l",str(binary)],stdout=subprocess.PIPE).stdout.decode(errors="replace")
                cryptids=re.findall(r"^\s*cryptid\s+(\d+)\s*$",load,re.M)
                nenc=len(re.findall(r"^\s*cmd LC_ENCRYPTION_INFO(?:_64)?\s*$",load,re.M))
                require(nenc==len(cryptids) and all(x=="0" for x in cryptids),"encrypted_or_invalid_image")
                relative=entry.filename[len(root):]
                image={"path":relative,"sha256":sha(binary),"cryptids":cryptids,"interfaces":metadata(binary,work)}
                report["images"].append(image)
                print("QQ_INTERFACE_IMAGE "+json.dumps(image,ensure_ascii=True),flush=True)
                if relative==info.get("CFBundleExecutable"): main_seen=True
                binary.unlink()
            require(main_seen,"main_executable_missing")
        report["status"]="static_metadata_only"
        report_dir=Path("qq-interface-report")
        report_dir.mkdir()
        (report_dir/"interfaces.json").write_text(json.dumps(report,indent=2))
        print("QQ_INTERFACE_SUMMARY "+json.dumps({k:v for k,v in report.items() if k!="images"}),flush=True)
if __name__=="__main__":
    try: main()
    except Rejected as e: raise SystemExit("QQ_INSPECTION_REJECTED "+str(e)) from None
    except Exception as e: raise SystemExit("QQ_INSPECTION_FAILED "+type(e).__name__) from None
