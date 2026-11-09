"""Read the already-sealed native error; no model use, decryption attempt or Apple calls."""
import json
import os
from pathlib import Path
import tempfile
from tf_virtual_native_error_restore import restore
def error_source(note,source=Path("native-source/unfairplay")):
    import re
    matches=[]
    for folder in ("internal","cmd"):
        for path in sorted((source/folder).rglob("*.go")):
            if path.name.endswith("_test.go"):continue
            for number,line in enumerate(path.read_text().splitlines(),1):
                found=re.search(r'(?:fmt.Errorf|errors.New)\("((?:[^"\\]|\\.)*)"',line)
                if not found:continue
                try:template=json.loads('"'+found[1]+'"')
                except Exception:continue
                pieces=re.split(r'%[-+ #0-9.]*[a-zA-Z]',template)
                weight=sum(len(piece) for piece in pieces)
                if weight<16:continue
                pattern=".*?".join(re.escape(piece) for piece in pieces)
                if re.search(pattern,note,re.S):
                    matches.append((weight,str(path.relative_to(source)),number))
    if not matches:return {"matched":False}
    weight,path,line=max(matches)
    return {"matched":True,"public_source":path,"line":line}

def main():
    env=dict(os.environ);os.umask(0o077)
    result={"schema":"tf-native-error-inspection-v1","status":"inspection_failed","apple_requests":0,"model_used":False,"decryption_proven":False}
    try:
        with tempfile.TemporaryDirectory(dir=env["RUNNER_TEMP"],prefix="tf-error-offline-") as folder:
            root=Path(folder);root.chmod(0o700);restore(root,env)
            path=root/"tf-model-verification-error.txt"
            if not path.is_file() or path.stat().st_size>32768:raise ValueError()
            note=path.read_text()
            result["error_source"]=error_source(note)
            words=("panic","runtime","fatal","flag","permission","permitted","directory","file","invalid","argument","signature",
                "CodeDirectory","pre-encryption","plaintext","model","key","selector","zip","compression","unsupported",
                "alignment","SIG","hash","export","cipher","EOF","open","stat","decrypt","account","page","size","report","APP","path")
            result["known_terms"]=[word for word in words if word.casefold() in note.casefold()]
            result["error_bytes"]=path.stat().st_size
            result["status"]="inspection_complete"
    except Exception:pass
    Path("tf-beta-receipt.json").write_text(json.dumps(result,sort_keys=True))
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0 if result["status"]=="inspection_complete" else 2
if __name__=="__main__":raise SystemExit(main())
