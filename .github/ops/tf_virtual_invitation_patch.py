"""Pinned fixed-invitation GET adapter; no acceptance/POST implementation."""
import hashlib
from pathlib import Path
import sys
def patch(path,expected,old,new):
    raw=path.read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=expected:raise ValueError("tf_invitation_source_mismatch")
    source=raw.decode()
    if source.count(old)!=1:raise ValueError("tf_invitation_anchor_invalid")
    path.write_text(source.replace(old,new))
if __name__=="__main__":
    patch(Path(sys.argv[1]),"7b80a7369dd24dbf4882d2bee623a9e0f26945a3",
        "    Json catalog();","    Json catalog();\n    Json invitation_info();")
    patch(Path(sys.argv[2]),"30f6d768a6d57c403d283000bfceca91919221d2",
        "Json Engine::catalog() {",
        'Json Engine::invitation_info() {\n    return request(3, "ru/yoNuHexZ");\n}\n\nJson Engine::catalog() {')
