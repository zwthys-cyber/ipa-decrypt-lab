"""GitHub-only streaming authenticated-envelope inventory. Retains only already-encrypted TF carrier."""
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import sys
import tarfile
PROMOTED="8349899c8806e2481edfc6f8f532d6aaa855f32c241b86951a03ea62df799765"
def need(ok):
    if not ok:raise ValueError("preservation_verification_failed")
def verify(stream,output):
    records={};manifest=None;session=None;total=0
    with tarfile.open(fileobj=stream,mode="r|gz") as archive:
        for member in archive:
            name=member.name;path=PurePosixPath(name)
            need(member.isfile() and name not in records and name==path.as_posix() and
                not path.is_absolute() and all(p not in (".","..") for p in path.parts) and
                (name=="manifest.json" or name=="config/bot.json" or name.startswith("state/")) and
                len(records)<501 and 0<=member.size<=100*1024*1024)
            total+=member.size;need(total<=101*1024*1024)
            source=archive.extractfile(member)
            if name=="manifest.json":
                need(manifest is None and member.size<=65536);manifest=json.loads(source.read());continue
            digest=hashlib.sha256();size=0;chunks=[]
            while True:
                chunk=source.read(1024*1024)
                if not chunk:break
                digest.update(chunk);size+=len(chunk)
                if name=="state/testflight/session.age":
                    need(size<=256*1024);chunks.append(chunk)
            need(size==member.size);records[name]=dict(bytes=size,sha256=digest.hexdigest())
            if name=="state/testflight/session.age":session=b"".join(chunks)
    # Drain the outer age reader so its complete authentication tag is checked.
    while stream.read(1024*1024):pass
    need(manifest and manifest.get("schema")=="ipa-online-preservation-v1" and manifest.get("frozen") is False and
        manifest.get("cutover_approved") is False and manifest.get("files")==records and
        session and session.startswith(b"age-encryption.org/v1\n") and hashlib.sha256(session).hexdigest()==PROMOTED and
        manifest.get("session_sha256")==PROMOTED)
    output=Path(output);output.mkdir(mode=0o700,exist_ok=True)
    with os.fdopen(os.open(output/"tf-session.age",os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),"wb") as dest:
        dest.write(session)
    receipt=dict(schema="ipa-online-preservation-receipt-v1",archive_verified=True,frozen=False,cutover_approved=False,
        files=len(records),session_matches_promoted=True,session_sha256=PROMOTED,
        acceptance_ledger_present="state/testflight/acceptance.sqlite" in records,
        task_states=manifest["task_states"])
    (output/"receipt.json").write_text(json.dumps(receipt,sort_keys=True)+"\n")
    return receipt
def main():
    try:
        need(os.environ.get("GITHUB_ACTIONS")=="true")
        print(json.dumps(verify(sys.stdin.buffer,Path("preservation-output")),sort_keys=True));return 0
    except Exception:
        print("preservation_verification_failed",file=sys.stderr);return 2
if __name__=="__main__":raise SystemExit(main())
