import hashlib, json, os, plistlib, re, subprocess, tempfile, zipfile
from pathlib import Path
import qq_metadata as meta
root=Path(os.environ["RUNNER_TEMP"])/"qq-private"
root.mkdir(mode=0o700, exist_ok=True)
try:
    archive=root/"artifact.zip"
    with archive.open("wb") as out:
        subprocess.run(["gh","api","repos/zwthys-cyber/ipa-decrypt-lab/actions/artifacts/14701130430/zip"],stdout=out,check=True)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=="d96191a8e1c3559dfe47c4e8a316202b82d9d941417acbf91817bdb07df5a9b1"
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        payload=[n for n in names if n.endswith("package.ipa.age")]
        assert len(payload)==1
        cipher=root/"package.age"; cipher.write_bytes(z.read(payload[0]))
    identity=root/"identity"; identity.write_text(os.environ["DELIVERY_AGE_IDENTITY"]+"\n"); identity.chmod(0o600)
    ipa=root/"package.ipa"
    subprocess.run(["age","--decrypt","-i",str(identity),"-o",str(ipa),str(cipher)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    meta.SELECTED=re.compile(r"(?!)")
    meta.SELECTOR=re.compile(r"screen.*(?:record|captur)|(?:record|captur).*screen|recording|recordState|recordStatus",re.I)
    results=[]
    with zipfile.ZipFile(ipa) as z:
        infos=[n for n in z.namelist() if re.fullmatch(r"Payload/[^/]+\.app/Info.plist",n)]
        assert len(infos)==1
        info=plistlib.loads(z.read(infos[0]))
        assert info["CFBundleIdentifier"]=="com.tencent.mqq"
        version={k:info.get(k) for k in ("CFBundleIdentifier","CFBundleShortVersionString","CFBundleVersion")}
        print(json.dumps({"version":version}))
        for entry in z.infolist():
            if entry.file_size<32 or entry.file_size>1500000000: continue
            with z.open(entry) as f: magic=f.read(4)
            if magic!=b"\xcf\xfa\xed\xfe": continue
            binary=root/"image"
            with z.open(entry) as f, binary.open("wb") as out:
                import shutil
                shutil.copyfileobj(f,out)
            try:
                methods=meta.inspect(binary)
            except meta.MetadataError:
                continue
            if methods:
                results.append({"image":entry.filename.split(".app/",1)[-1],"sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"methods":methods})
    Path("qq-call-metadata.json").write_text(json.dumps({"version":version,"images":results},indent=2))
    for result in results:
        print(json.dumps(result))
finally:
    import shutil
    shutil.rmtree(root,ignore_errors=True)
