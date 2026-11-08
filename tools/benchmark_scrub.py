"""GitHub-only synthetic comparison; no application or account material."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
import time
import zipfile
from private_export import scrub_archive

def member_hash(archive,entry):
    value=hashlib.sha256()
    with archive.open(entry) as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            value.update(block)
    return value.hexdigest()

def main():
    if os.environ.get("GITHUB_ACTIONS")!="true":
        raise SystemExit("requires_github_actions")
    p=argparse.ArgumentParser();p.add_argument("--crypt",required=True);args=p.parse_args()
    crypt=str(Path(args.crypt).resolve())
    with tempfile.TemporaryDirectory(prefix="synthetic-scrub-") as directory:
        root=Path(directory);source=root/"source.ipa"
        generator=random.Random(271)
        with zipfile.ZipFile(source,"w",compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("iTunesMetadata.plist",b"synthetic-account-fixture")
            z.writestr("Payload/Fixture.app/SC_Info/test.sinf",b"synthetic-license-fixture")
            with z.open("Payload/Fixture.app/assets","w") as f:
                for _ in range(32):f.write(generator.randbytes(1024*1024))
            with z.open("Payload/Fixture.app/code","w") as f:
                for _ in range(32):f.write(b"public-synthetic-code"*52428)
        times={};outputs={}
        for name,helper in (("reference",None),("raw_copy",crypt)):
            target=root/(name+".ipa");start=time.perf_counter()
            scrub_archive(source,target,crypt=helper)
            times[name]=round(time.perf_counter()-start,6);outputs[name]=target
        with zipfile.ZipFile(source) as original:
            expected={e.filename:member_hash(original,e) for e in original.infolist() if e.filename.startswith("Payload/Fixture.app/") and "/SC_Info/" not in e.filename}
        for target in outputs.values():
            with zipfile.ZipFile(target) as z:
                assert z.testzip() is None
                assert {e.filename:member_hash(z,e) for e in z.infolist()}==expected
        result={"schema":"ipa-scrub-benchmark-v1","synthetic":True,"source_bytes":source.stat().st_size,
                "reference_seconds":times["reference"],"raw_copy_seconds":times["raw_copy"],
                "raw_copy_bytes":outputs["raw_copy"].stat().st_size,"retained_contents_match":True,"output_crc_verified":True}
        Path("scrub-benchmark.json").write_text(json.dumps(result)+"\n")
        print(json.dumps(result))
if __name__=="__main__":main()
