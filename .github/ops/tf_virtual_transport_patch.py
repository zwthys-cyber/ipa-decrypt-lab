"""Pinned, isolated GSA connection-reuse control; no credentials or wire payload logging."""
import hashlib
from pathlib import Path
import sys

BLOB="e30e1a2294fda8396e54210546db3c54a4e384ac"
ANCHOR="    const auto status = curl_easy_perform(handle.get());"
INSERT=r'''
    const char* lab_phase = "other";
    if (url.find("/grandslam/GsService2/lookup") != std::string::npos) {
        lab_phase = "lookup";
    } else if (url.find("/grandslam/GsService2") != std::string::npos) {
        const std::string payload(body.begin(), body.end());
        lab_phase = payload.find("<string>init</string>") != std::string::npos ? "srp_init" :
                    payload.find("<string>complete</string>") != std::string::npos ? "srp_complete" : "gsa_service";
    }
    const char* lab_control = std::getenv("TF_CURL_FRESH_GSA");
    const bool lab_fresh = std::string(lab_phase) != "other" &&
                           lab_control && std::string(lab_control) == "1";
    if (lab_fresh) {
        curl_easy_setopt(handle.get(), CURLOPT_FRESH_CONNECT, 1L);
        curl_easy_setopt(handle.get(), CURLOPT_FORBID_REUSE, 1L);
    }
    const auto status = curl_easy_perform(handle.get());
    if (std::string(lab_phase) != "other") {
        double connected=0, tls=0, first=0, total=0;
        long http=0, connections=0, version=0;
        curl_off_t uploaded=0, downloaded=0;
        curl_easy_getinfo(handle.get(), CURLINFO_CONNECT_TIME, &connected);
        curl_easy_getinfo(handle.get(), CURLINFO_APPCONNECT_TIME, &tls);
        curl_easy_getinfo(handle.get(), CURLINFO_STARTTRANSFER_TIME, &first);
        curl_easy_getinfo(handle.get(), CURLINFO_TOTAL_TIME, &total);
        curl_easy_getinfo(handle.get(), CURLINFO_RESPONSE_CODE, &http);
        curl_easy_getinfo(handle.get(), CURLINFO_NUM_CONNECTS, &connections);
        curl_easy_getinfo(handle.get(), CURLINFO_HTTP_VERSION, &version);
        curl_easy_getinfo(handle.get(), CURLINFO_SIZE_UPLOAD_T, &uploaded);
        curl_easy_getinfo(handle.get(), CURLINFO_SIZE_DOWNLOAD_T, &downloaded);
        std::fprintf(stderr,
            "TF_NET:{\"phase\":\"%s\",\"fresh_connection\":%s,\"curl_exit\":%d,\"http_status\":%ld,"
            "\"connect_ms\":%lld,\"tls_ms\":%lld,\"first_byte_ms\":%lld,\"total_ms\":%lld,"
            "\"upload_complete\":%s,\"received_body\":%s,\"new_connections\":%ld,\"http_version\":%ld}\n",
            lab_phase, lab_fresh ? "true" : "false", static_cast<int>(status), http,
            static_cast<long long>(connected*1000), static_cast<long long>(tls*1000),
            static_cast<long long>(first*1000), static_cast<long long>(total*1000),
            !body.empty() && uploaded >= static_cast<curl_off_t>(body.size()) ? "true" : "false",
            downloaded>0 ? "true" : "false", connections, version);
        std::fflush(stderr);
    }
'''
def patch(raw):
    digest=hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()
    if digest!=BLOB:raise ValueError("tf_transport_source_mismatch")
    source=raw.decode()
    if source.count(ANCHOR)!=1:raise ValueError("tf_transport_anchor_mismatch")
    return source.replace("#include <array>","#include <array>\n#include <cstdio>\n#include <cstdlib>").replace(ANCHOR,INSERT)

if __name__=="__main__":
    path=Path(sys.argv[1])
    path.write_text(patch(path.read_bytes()))
