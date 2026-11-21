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
class SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
        import urllib.parse
        require(urllib.parse.urlsplit(newurl).scheme=="https","non_https_redirect")
        if urllib.parse.urlsplit(newurl).netloc!=urllib.parse.urlsplit(req.full_url).netloc:
            redirected.remove_header("Authorization")
        return redirected
def api(path):
    report["stage"]="artifact_metadata" if not path.endswith("/zip") else "artifact_download"
    req=urllib.request.Request("https://api.github.com/repos/"+REPO+path,headers={"Authorization":"Bearer "+os.environ["GH_TOKEN"],"Accept":"application/vnd.github+json"})
    return urllib.request.build_opener(SafeRedirects()).open(req,timeout=90)
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
          methods=[]
          metadata_errors=[]
          for sec,address,length in im.sections:
            if sec!="__objc_classlist":continue
            for position in range(address,address+length,8):
              try:
                cls=im.pointer(position)
                if not cls:continue
                ro=im.pointer(cls+32)&~7
                name=im.string(im.pointer(ro+24))
                methods.extend(im.methods(im.pointer(ro+32),name,False))
                meta=im.pointer(cls)
                if meta:
                  mro=im.pointer(meta+32)&~7
                  methods.extend(im.methods(im.pointer(mro+32),name,True))
              except MetadataError as exc:
                metadata_errors.append(str(exc))
          for sec,address,length in im.sections:
            if sec!="__objc_catlist":continue
            for position in range(address,address+length,8):
              try:
                cat=im.pointer(position);cls=im.pointer(cat+8)
                if not cls:continue
                ro=im.pointer(cls+32)&~7
                name=im.string(im.pointer(ro+24))
                category=im.string(im.pointer(cat))
                for is_meta,off in ((False,16),(True,24)):
                  entries=im.methods(im.pointer(cat+off),name,is_meta)
                  for entry in entries:entry["category"]=category
                  methods.extend(entries)
              except MetadataError as exc:metadata_errors.append(str(exc))
          record["metadata_error_counts"]={x:metadata_errors.count(x) for x in set(metadata_errors)}
          record["focused_strings"]=[]
          for match in re.finditer(rb"[\x20-\x7e]{5,600}",data):
            text=match.group().decode("ascii")
            if re.search(r"AVVideoRecord|QAVVideoRecord|QQAVReplayKit|QQAVTinyVideo|IQQAVTinyVideo",text) and len(text)<=500:
              record["focused_strings"].append(text)
          record["focused_strings"]=list(dict.fromkeys(record["focused_strings"]))[:600]
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
        hot=re.compile(r"notifyPeerRecord|handlePeerRecord|setPeerRecordState|onRecordStart|recordAVTinyVideoFinished|onRecordStopReason|notify.*record|record.*notify",re.I)
        recorder_hot=re.compile(r"^(?:init|setUpWriter|startRecord|startMultiSoundRecord|startRecordWithMultiSound:|writeAudioData|roomAudioData:|doAudioReceiveData:type:|addAudioData:|stopRecordingWithStopReason:recordTime:Completion:)$")
        chosen=[m for m in methods if hot.search(m["selector"]) or (m["class"]=="QQAVTinyVideoRecorder" and recorder_hot.search(m["selector"])) or (m["class"]=="QAVRecordPanel" and re.search(r"^(?:startRecord|stopRecord)$",m["selector"]))]
        chosen=chosen[:70]
        report["chosen_methods_count"]=len(chosen)
        def stub_selector(address):
          try:
            off,_=im.location(address,12)
            a,b=struct.unpack_from("<II",data,off)
            if a&0x9f000000!=0x90000000:return None
            imm=((a>>29)&3)|(((a>>5)&0x7ffff)<<2)
            if imm&(1<<20):imm-=1<<21
            page=(address&~4095)+(imm<<12)
            if b&0xffc00000!=0xf9400000 or (b&31)!=1 or ((b>>5)&31)!=(a&31):return None
            ref=page+((b>>10)&0xfff)*8
            return im.string(im.pointer(ref))
          except (MetadataError,struct.error):return None
        # GNU mode honors address bounds for Mach-O; public output is restricted
        # to selected function instructions, not arbitrary resource strings.
        for m in chosen:
          start=int(m["imp"],16)
          args=["llvm-objdump","--disassemble","--no-show-raw-insn","--start-address="+hex(start),"--stop-address="+hex(start+2048),str(image)]
          p=run(args)
          if p.returncode==0:
            text=p.stdout.decode("utf-8","replace")
            calls={}
            for target in re.findall(r"\b(?:bl|b)\s+(0x[0-9a-f]+)",text):
              selector=stub_selector(int(target,16))
              if selector:calls[target]=selector
            record["disassembly"].append({"method":m,"text":text[:50000],"objc_calls":calls})
          else:
            record["disassembler_error"]=p.stderr.decode("utf-8","replace")[:500];break
        # Resolve method selector and CFString references for later cross-reference work.
        record["constant_strings"]=[]
        for sec,addr,size in im.sections:
          if sec!="__cfstring":continue
          for pos in range(addr,addr+size,32):
            try:
              flags=im.integer(pos+8,"<Q")
              pointer=im.pointer(pos+16);length=im.integer(pos+24,"<Q")
              if not 0<length<=500:continue
              unicode=bool(flags&0x10)
              offset,_=im.location(pointer,length*(2 if unicode else 1))
              value=data[offset:offset+length*(2 if unicode else 1)].decode("utf-16-le" if unicode else "utf-8")
              if re.search(r"录制|录屏|录音|record.{0,12}(?:call|screen)|(?:call|screen).{0,12}record",value,re.I) and valid_text(value):
                record["constant_strings"].append({"address":hex(pos),"text":value,"file_offset":hex(offset)})
            except (MetadataError,UnicodeError):pass
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
    if isinstance(exc,urllib.error.HTTPError):report["http_status"]=exc.code
finally:
    (OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({"status":report["status"],"version":report.get("version"),"image_count":len(report.get("images",[]))}))
if report["status"]=="failed":sys.exit(1)
