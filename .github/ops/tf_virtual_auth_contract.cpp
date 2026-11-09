#include "client/client_internal.hpp"
#include <stdexcept>
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT int lab_tf_auth_contract() {
    using namespace netdetail;
    try {
        for(const auto* value : {
            R"({"Status":{"ec":0}})", R"({"Response":{"Status":{"ec":0}}})",
            R"({"ec":0})", R"({"Response":{"ec":0}})"}) {
            verify_grandslam_two_factor(Json::parse(value));
        }
        for(const auto* value : {
            R"({"Status":{}})",R"({"Status":{"ec":1}})",
            R"({"Response":{"Status":{"ec":false}}})",
            R"({"Response":{"Status":{"ec":"0"}}})",
            R"({"Response":{"Status":{"ec":0.0}}})",
            R"({"Status":{"ec":1},"Response":{"Status":{"ec":0}}})"}) {
            bool rejected=false;
            try { verify_grandslam_two_factor(Json::parse(value)); } catch(...) { rejected=true; }
            if(!rejected)return 2;
        }
        unsigned fresh=0, requests=0;bool complete=false, equal=false, proof_rejected=false;
        Json init_cpd;Headers init_headers;
        auto fresh_headers=[&]() {
            ++fresh;
            const auto token="SYNTHETIC-"+std::to_string(fresh);
            return Headers{{"X-Apple-I-MD",token},{"X-Apple-I-MD-M","SYNTHETIC"},
                {"X-Apple-I-MD-LU","SYNTHETIC"},{"X-Apple-I-MD-RINFO","1"},
                {"X-Mme-Device-Id","SYNTHETIC"},{"X-MMe-Client-Info","SYNTHETIC"},
                {"User-Agent","Synthetic/1"}};
        };
        Transport fake=[&](const HttpRequest& request) -> HttpResponse {
            ++requests;
            if(request.method=="GET") {
                return {200,encode_plist(Json{{"urls",{{"gsService","https://gsa.apple.com/grandslam/GsService2"}}}}),{}};
            }
            const auto fields=parse_plist(request.body).at("Request");
            if(fields.at("o")=="init") {
                init_cpd=fields.at("cpd");init_headers=request.headers;
                return {200,encode_plist(Json{{"Response",{
                    {"Status",{{"ec",0}}},{"i",1000},{"s",Json::binary(Bytes(16,1))},
                    {"B",Json::binary(Bytes(256,1))},{"c","SYNTHETIC"},{"sp","s2k"}}}}),{}};
            }
            complete=true;equal=fields.at("cpd")==init_cpd && request.headers==init_headers;
            return {200,encode_plist(Json{{"Response",{
                {"Status",{{"ec",0}}},{"M2",Json::binary(Bytes(32,0))},
                {"spd",Json::binary(Bytes(16,0))}}}}),{}};
        };
        try {
            (void)grandslam_login("fixture@example.invalid","SYNTHETIC",fresh_headers,
                []()->std::string{throw std::runtime_error("unexpected verification");},
                fake,[](){return std::int64_t(1700000000);},nullptr);
        } catch(const std::exception& error) {
            proof_rejected=std::string(error.what())=="SrpHandshake server proof is invalid";
        }
        return fresh==2 && requests==3 && complete && equal && proof_rejected ? 0 : 2;
    } catch(...) { return 2; }
}
}
