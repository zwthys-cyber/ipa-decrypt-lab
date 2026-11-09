"""Pinned fixed yoNuHexZ read/accept adapter; POST has an empty body and no retry."""
import hashlib
from pathlib import Path
import sys
def patch(path,expected,replacements):
    raw=path.read_bytes()
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=expected:raise ValueError("tf_invitation_source_mismatch")
    source=raw.decode()
    for old,new in replacements:
        if source.count(old)!=1:raise ValueError("tf_invitation_anchor_invalid")
        source=source.replace(old,new)
    path.write_text(source)
if __name__=="__main__":
    patch(Path(sys.argv[1]),"7b80a7369dd24dbf4882d2bee623a9e0f26945a3",[
        ("    Json catalog();","    Json catalog();\n    Json invitation_info();\n    Json invitation_accept();\n    std::string invitation_app_binding(const std::string& bundle);"),
        ("const Json* body = nullptr);","const Json* body = nullptr, bool empty_post = false);")])
    patch(Path(sys.argv[2]),"30f6d768a6d57c403d283000bfceca91919221d2",[
        ("const Json* body) {","const Json* body, bool empty_post) {"),
        ('body ? "POST" : "GET"','(body || empty_post) ? "POST" : "GET"'),
        ("Json Engine::catalog() {",'Json Engine::invitation_info() {\n    return request(3, "ru/yoNuHexZ");\n}\n\nJson Engine::invitation_accept() {\n    return request(3, "ru/yoNuHexZ/accept", nullptr, true);\n}\n\nstd::string Engine::invitation_app_binding(const std::string& bundle) {\n    return find_app(bundle);\n}\n\nJson Engine::catalog() {')])
