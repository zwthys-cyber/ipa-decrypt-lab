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
        ("const Json* body = nullptr);","const Json* body = nullptr, bool empty_post = false);"),
        ("std::uint64_t\nunwrap_transport", "Path transport_archive(const Path& source,const Path& decrypted,View hardware,const Json& metadata);\n\nstd::uint64_t\nunwrap_transport")])
    patch(Path(sys.argv[2]),"30f6d768a6d57c403d283000bfceca91919221d2",[
        ("const Json* body) {","const Json* body, bool empty_post) {"),
        ('body ? "POST" : "GET"','(body || empty_post) ? "POST" : "GET"'),
        ("Json Engine::catalog() {",'Json Engine::invitation_info() {\n    return request(3, "ru/yoNuHexZ");\n}\n\nJson Engine::invitation_accept() {\n    return request(3, "ru/yoNuHexZ/accept", nullptr, true);\n}\n\nstd::string Engine::invitation_app_binding(const std::string& bundle) {\n    return find_app(bundle);\n}\n\nJson Engine::catalog() {'),
        ("#include <iomanip>","#include <iomanip>\n#include <fstream>"),
        ("require(data.is_object() && !text(data, \"url\").empty() && !text(data, \"dpInfo\").empty(),","require(data.is_object() && !text(data, \"url\").empty() && data.contains(\"dpInfo\") &&\n                (data.at(\"dpInfo\").is_null() || (data.at(\"dpInfo\").is_string() && !text(data,\"dpInfo\").empty())),"),
        ("TestFlightDownload\ndownload_testflight_ipa","Path transport_archive(const Path& source,const Path& decrypted,View hardware,const Json& metadata) {\n    require(metadata.is_object() && metadata.contains(\"dpInfo\"),\"Missing TestFlight transport mode\");\n    const auto& info=metadata.at(\"dpInfo\");\n    if(info.is_null()) {\n        std::ifstream input(source,std::ios::binary);\n        std::array<char,4> magic{};\n        input.read(magic.data(),magic.size());\n        require(input.gcount()==4 && magic[0]=='P' && magic[1]=='K' && magic[2]==3 && magic[3]==4,\n            \"Plain TestFlight transport is not a ZIP\");\n        return source;\n    }\n    require(info.is_string() && !info.get<std::string>().empty(),\"Invalid TestFlight transport metadata\");\n    unwrap_transport(source,decrypted,hardware,unbase64(info.get<std::string>()));\n    return decrypted;\n}\n\nTestFlightDownload\ndownload_testflight_ipa"),
        ("    unwrap_transport(work / \"transport.bin\",\n                     work / \"applezip.ipa\",\n                     client.hardware(),\n                     unbase64(text(metadata, \"dpInfo\")));\n    auto archive = normalize_ipa(work / \"applezip.ipa\", destination, bundle, sinfs);","    const auto archive_source=transport_archive(work/\"transport.bin\",work/\"applezip.ipa\",client.hardware(),metadata);\n    auto archive = normalize_ipa(archive_source, destination, bundle, sinfs);")])
