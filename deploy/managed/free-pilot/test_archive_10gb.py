"""CI-only exact 10 GB sparse synthetic ZIP64 archive full-read contract.

No network, app data, credentials, persistent fixture, or production upload.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import time
import zipfile

import archive_verify as v

LIMIT=10_000_000_000
BLOCK=b"\0"*(8*1024*1024)

class SparseSink:
    def __init__(self,stream):self.stream=stream
    def tell(self):return self.stream.tell()
    def seek(self,*args):return self.stream.seek(*args)
    def flush(self):return self.stream.flush()
    def write(self,data):
        if len(data)==len(BLOCK) and data==BLOCK:
            self.stream.seek(len(data),os.SEEK_CUR)
            return len(data)
        return self.stream.write(data)

def main():
    assert v.MAX_ARCHIVE==LIMIT
    with tempfile.TemporaryDirectory() as directory:
        p=Path(directory)/"Synthetic.ipa"
        started=time.monotonic()
        with p.open("w+b") as stream:
            with zipfile.ZipFile(SparseSink(stream),"w",compression=zipfile.ZIP_STORED,allowZip64=True) as z:
                z.writestr("Payload/Synthetic.app/Info.plist",b"synthetic layout only")
                with z.open("Payload/Synthetic.app/zeros.bin","w",force_zip64=True) as member:
                    count,tail=divmod(LIMIT-4096,len(BLOCK))
                    for _ in range(count):member.write(BLOCK)
                    member.write(BLOCK[:tail])
                z.writestr("Payload/Synthetic.app/tail.txt",b"marker")
            stream.flush()
            padding=LIMIT-os.fstat(stream.fileno()).st_size
            assert 0<=padding<=65535
            with zipfile.ZipFile(stream,"a",allowZip64=True) as z:
                z.comment=b"x"*padding
            stream.flush()
            os.fchmod(stream.fileno(),0o600)
            stat=os.fstat(stream.fileno())
            assert stat.st_size==LIMIT and stat.st_blocks*512<16*1024*1024
            stream.seek(0)
            expected=hashlib.file_digest(stream,"sha256").hexdigest()
            build_seconds=time.monotonic()-started
            t=time.monotonic()
            result=v.verify(stream,ipa=True,expected=expected)
            seconds=time.monotonic()-t
            assert result["archive_bytes"]==LIMIT and result["zip64"] is True
            assert result["all_member_crc_verified"] and result["expected_sha256_matched"]
            assert result["entries"]==3 and result["authenticity_verified"] is False
            stream.seek(0,os.SEEK_END);stream.write(b"x");stream.flush()
            try:v.verify(stream,ipa=True)
            except v.VerificationError as exc:assert str(exc)=="archive_size_out_of_bounds"
            else:raise AssertionError("oversize not rejected")
            print(json.dumps({"synthetic_archive_bytes":LIMIT,"physical_allocated_bytes":stat.st_blocks*512,
                "all_member_crc_verified":True,"independent_sha256_matched":True,"oversize_rejected":True,
                "fixture_and_reference_hash_seconds":round(build_seconds,3),"verification_seconds":round(seconds,3),
                "peak_rss_kib":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},sort_keys=True),flush=True)

if __name__=="__main__":main()
