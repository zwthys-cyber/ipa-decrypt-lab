"""Isolated pinned GSA compatibility fixes; retain explicit OTP and SRP proof checks."""
import hashlib
from pathlib import Path
import sys
BLOB="85cd944253fc0954d05fe578094c78ff46b3854d"
OLD_PAIR='''        Headers headers;
        auto post = [&](Json fields) {
            headers = authentication_headers(fresh_headers, clock());
            fields["cpd"] = client_data(headers);'''
NEW_PAIR='''        Headers headers = authentication_headers(fresh_headers, clock());
        const auto exchange_data = client_data(headers);
        auto post = [&](Json fields) {
            fields["cpd"] = exchange_data;'''
OLD_VERIFY='''    const auto& result = response.contains("Status") ? response.at("Status") : response;
    require(result.is_object() && result.contains("ec") && result.at("ec").is_number_integer() &&
                result.at("ec").get<std::int64_t>() == 0,
            "Apple did not confirm the 2FA code");'''
NEW_VERIFY=r'''    require(response.is_object(), "Apple did not confirm the 2FA code");
    const auto& payload = response.contains("Response") ? response.at("Response") : response;
    require(payload.is_object(), "Apple did not confirm the 2FA code");
    if (response.contains("Response") && response.contains("Status")) {
        require(payload.contains("Status") && response.at("Status") == payload.at("Status"),
                "Apple did not confirm the 2FA code");
    }
    const auto& result = payload.contains("Status") ? payload.at("Status") : payload;
    const bool object = result.is_object();
    const bool present = object && result.contains("ec");
    const bool integer = present && result.at("ec").is_number_integer();
    const auto numeric = integer ? result.at("ec").get<std::int64_t>() : 0;
    const bool in_range = integer && numeric >= -99999999 && numeric <= 99999999;
    const char* envelope = response.contains("Response") ? "response" :
                           response.contains("Status") ? "status" : "top";
    std::fprintf(stderr,
        "TF_VERIFY:{\"envelope\":\"%s\",\"object\":%s,\"ec_present\":%s,\"ec_integer\":%s,"
        "\"ec_in_range\":%s,\"ec_code\":%lld}\n",
        envelope, object ? "true" : "false", present ? "true" : "false",
        integer ? "true" : "false", in_range ? "true" : "false",
        static_cast<long long>(in_range ? numeric : 0));
    std::fflush(stderr);
    require(object && integer && in_range && numeric == 0,
            "Apple did not confirm the 2FA code");'''
def patch(raw):
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=BLOB:
        raise ValueError("tf_auth_source_mismatch")
    source=raw.decode()
    if source.count(OLD_PAIR)!=1 or source.count(OLD_VERIFY)!=1:
        raise ValueError("tf_auth_anchor_mismatch")
    return source.replace("#include <algorithm>","#include <algorithm>\n#include <cstdio>").replace(OLD_PAIR,NEW_PAIR).replace(OLD_VERIFY,NEW_VERIFY)
if __name__=="__main__":
    path=Path(sys.argv[1]);path.write_text(patch(path.read_bytes()))
