import os, sys, json, hashlib, urllib.request, zipfile, tempfile, pathlib, subprocess, re, mmap, struct, traceback
from objc_metadata import Image, MetadataError
import objc_metadata as om
REPO="zwthys-cyber/ipa-decrypt-lab"
RUN=44887720434
ARTIFACT=14701130430
EXPECTED_ZIP="d96191a8e1c3559dfe47c4e8a316202b82d9d941417acbf91817bdb07df5a9b1"
OUT=pathlib.Path(os.environ["RUNNER_TEMP"])/"qq-call-report"
OUT.mkdir(mode=0o700,exist_ok=True)
def require(x,why):
    if not x: raise ValueError(why)
def digest(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()
def api(path):
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+path,headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json"})
    return urllib.request.urlopen(req,timeout=90)
def run(args,**kw):
    env={k:os.environ[k] for k in ("PATH","HOME","LANG","TMPDIR") if k in os.environ}
    return subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180,**kw)
def bundle_info(z):
    roots=[n[:-10] for n in z.namelist() if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist",n)]
    require(len(roots)==1,"ambiguous_main_bundle")
    import plistlib
    root=roots[0]
    return root,plistlib.loads(z.read(root+"Info.plist"))
def valid_text(s):
    return len(s)<=300 and all(c.isprintable() or c in "\n\t" for c in s)
report={"schema":"qq-call-record-static-v1","source_run":RUN,"runtime_verified":False,"status":"incomplete"}
try:
  with tempfile.TemporaryDirectory(prefix="qq-call-private-") as td:
    td=pathlib.Path(td);td.chmod(0o700)
    meta=json.load(api("/actions/artifacts/"+str(ARTIFACT)))
    require(not meta["expired"] and meta["workflow_run"]["id"]==RUN and meta["digest"]=="sha256:"+EXPECTED_ZIP,"artifact_provenance_mismatch")
    archive=td/"carrier.zip"
    with api("/actions/artifacts/"+str(ARTIFACT)+"/zip") as src,open(archive,"wb") as dst:
        import shutil
        shutil.copyfileobj(src,dst)
    require(digest(archive)==EXPECTED_ZIP,"carrier_digest_mismatch")
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist())=={"receipt.json","package.ipa.age"},"unexpected_delivery_inventory")
        receipt=json.loads(z.read("receipt.json"))
        require(receipt["run_id"]==str(RUN) and receipt["app_id"]=="444934666" and receipt["plaintext_verified"] is True and receipt["account_data_removed"] is True,"receipt_binding_mismatch")
        cipher=td/"package.ipa.age";cipher.write_bytes(z.read("package.ipa.age"))
    require(digest(cipher)==receipt["ciphertext_sha256"],"cipher_digest_mismatch")
    ipa=td/"package.ipa"
    key=os.environ.pop("DELIVERY_AGE_IDENTITY","").strip()
    require(key.startswith("AGE-SECRET-KEY-"),"missing_delivery_identity")
    p=run(["age","-d","-i","-","-o",str(ipa),str(cipher)],input=(key+"\n").encode())
    key=""
    require(p.returncode==0 and digest(ipa)==receipt["plaintext_sha256"],"authenticated_delivery_decryption_failed")
    report["plaintext_sha256"]=receipt["plaintext_sha256"]
    with zipfile.ZipFile(ipa) as z:
      root,info=bundle_info(z)
      require(info["CFBundleIdentifier"]=="com.tencent.mqq","not_qq")
      report["version"]={"short":info.get("CFBundleShortVersionString"),"build":info.get("CFBundleVersion")}
      main=root+info["CFBundleExecutable"]
      report["ui_resources"]=[]
      for e in z.infolist():
        if e.file_size>3*1024*1024 or e.is_dir():continue
        if not e.filename.endswith((".strings",".stringsdict",".json",".plist")):continue
        if not e.filename.startswith(root):continue
        data=z.read(e)
        items=[]
        try:
          import plistlib
          obj=plistlib.loads(data)
          def walk(v,path=""):
            if isinstance(v,dict):
              for k,w in v.items():walk(w,path+"/"+str(k))
            elif isinstance(v,list):
              for i,w in enumerate(v):walk(w,path+"/"+str(i))
            elif isinstance(v,str) and re.search(r"录制|录屏|通话录音|双方声音|record.{0,12}(?:call|screen)|(?:call|screen).{0,12}record",v,re.I) and valid_text(v):
              items.append({"key":path[-180:],"value":v})
          walk(obj)
        except Exception:
          for enc in ("utf-8","utf-16"):
            try:
              txt=data.decode(enc)
              for line in txt.splitlines():
                if re.search(r"录制|录屏|通话录音|双方声音",line) and valid_text(line):
                  items.append({"line":line})
              break
            except UnicodeError:pass
        if items:report["ui_resources"].append({"resource":e.filename[len(root):],"matches":items[:35]})
        if sum(len(i["matches"]) for i in report["ui_resources"])>=400:break
      report["images"]=[]
      names=[main]+[e.filename for e in z.infolist() if e.filename.startswith(root+"Frameworks/") and re.search(r"(?:av|rtc|voip|call)",e.filename,re.I) and e.file_size>1024*1024 and not e.filename.endswith((".a",".metallib",".png",".car"))]
      for num,name in enumerate(names[:35]):
        data=z.read(name)
        if data[:4]!=b"\xcf\xfa\xed\xfe":continue
        image=td/("image-"+str(num));image.write_bytes(data)
        record={"name":name[len(root):],"sha256":hashlib.sha256(data).hexdigest(),"methods":[],"candidate_strings":[],"disassembly":[]}
        im=Image(data)
        commands,=struct.unpack_from("<I",data,16)
        pos=32;cryptids=[]
        for _ in range(commands):
          cmd,size=struct.unpack_from("<II",data,pos)
          if cmd in (0x21,0x2c):cryptids.append(struct.unpack_from("<I",data,pos+16)[0])
          pos+=size
        require(all(v==0 for v in cryptids),"image_encrypted")
        record["cryptids"]=cryptids
        om.SELECTED=re.compile(r".*(?:QQAV|QAV|AVChat|QQCall|QCall|VideoChat|VideoCall|AV.*Record|Record.*AV|ScreenRecord|CallRecord|TRTC).*",re.I)
        om.SELECTOR=re.compile(r"screenRecord|recordScreen|recordCall|callRecord|startRecord|stopRecord|recordAudio|audioRecord|recordVideo|videoRecord|replayKit|captureScreen",re.I)
        try:
          methods=im.inspect()
          record["methods"]=methods[:14000]
          require(len(methods)<=14000,"method_report_bound")
        except Exception as exc:
          record["metadata_error"]=type(exc).__name__
          methods=[]
        seen=set()
        hints=re.compile(r"(?:screen.?record|record.?screen|call.?record|record.?call|replaykit|record.{0,25}(?:audio|video|avchat)|(?:audio|video|avchat).{0,25}record)",re.I)
        for m in re.finditer(rb"[\x20-\x7e]{5,400}",data):
          s=m.group().decode("ascii")
          if hints.search(s) and len(s)<=200 and s not in seen and not re.search(r"https?://|token|secret|password",s,re.I):
            seen.add(s);record["candidate_strings"].append(s)
          if len(seen)>=500:break
        record["chinese_strings"]=[]
        for term in ("录制","录屏","通话录音"):
          term_b=term.encode()
          start=0
          for _ in range(150):
            at=data.find(term_b,start)
            if at<0:break
            start=at+len(term_b)
            left=data.rfind(b"\0",max(0,at-150),at)+1
            right=data.find(b"\0",at,min(len(data),at+250))
            if right<0:continue
            try:s=data[left:right].decode("utf-8")
            except UnicodeError:continue
            if valid_text(s):record["chinese_strings"].append({"text":s,"file_offset":hex(left)})
        chosen=[m for m in methods if re.search(r"record|replay|capture",m["selector"],re.I) and re.search(r"QAV|QQAV|AVChat|QQCall|QCall|VideoChat|VideoCall|ScreenRecord|CallRecord",m["class"],re.I)]
        chosen=chosen[:70]
        # GNU mode honors address bounds for Mach-O; public output is restricted
        # to selected function instructions, not arbitrary resource strings.
        for m in chosen:
          start=int(m["imp"],16)
          args=["llvm-objdump","--disassemble","--no-show-raw-insn","--start-address="+hex(start),"--stop-address="+hex(start+384),str(image)]
          p=run(args)
          if p.returncode==0:
            text=p.stdout.decode("utf-8","replace")
            record["disassembly"].append({"method":m,"text":text[:18000]})
          else:
            record["disassembler_error"]=p.stderr.decode("utf-8","replace")[:500];break
        # Resolve method selector and CFString references for later cross-reference work.
        record["selector_refs"]={}
        for sec,addr,size in im.sections:
          if sec!="__objc_selrefs":continue
          for pos in range(addr,addr+size,8):
            try:
              s=im.string(im.pointer(pos))
              if re.search(r"record|capture|audio|microphone|replay",s,re.I):
                record["selector_refs"][hex(pos)]=s
            except MetadataError:pass
        report["images"].append(record)
        image.unlink()
    report["status"]="static_inspection_complete"
except Exception as exc:
    report["status"]="failed"
    report["error"]=str(exc) if isinstance(exc,ValueError) else type(exc).__name__
finally:
    (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({"status":report["status"],"version":report.get("version"),"image_count":len(report.get("images",[]))}))
if report["status"]=="failed":sys.exit(1)
