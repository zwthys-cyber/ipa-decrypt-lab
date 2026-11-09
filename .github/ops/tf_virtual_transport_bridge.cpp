#include "client/client_internal.hpp"
#include <algorithm>
#include <cctype>
#include <cstdio>
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT Transport lab_tf_curl_transport() {
    return netdetail::make_curl_transport();
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT bool lab_tf_account_session_valid(const AccountSession& account,std::int64_t now) {
    netdetail::Json summary={{"parsed",false},{"id_matches",false},{"pet_matches",false},
        {"expiry_kind","absent"},{"remaining_seconds",0},{"has_root_key",false},
        {"has_root_challenge",false},{"has_idms_token",false}};
    bool valid=false;
    try {
        const auto value=netdetail::parse_plist(account.plist);
        summary["parsed"]=true;
        summary["has_root_key"]=value.contains("sk") && value.at("sk").is_binary() && !value.at("sk").empty();
        summary["has_root_challenge"]=value.contains("c") &&
            (value.at("c").is_string() || value.at("c").is_binary()) && !value.at("c").empty();
        summary["has_idms_token"]=value.contains("GsIdmsToken") &&
            value.at("GsIdmsToken").is_string() && !value.at("GsIdmsToken").get<std::string>().empty();
        const auto& pet=value.at("t").at("com.apple.gs.idms.pet");
        summary["id_matches"]=value.at("adsid")==account.account_id;
        summary["pet_matches"]=pet.at("token")==account.pet;
        if(pet.contains("expiry")) {
            const auto& expiry=pet.at("expiry");
            summary["expiry_kind"]=expiry.is_number_integer() ? "integer" :
                expiry.is_number_float() ? "floating" : expiry.is_string() ? "string" : "other";
            if(expiry.is_number_integer()) {
                const auto remaining=expiry.get<std::int64_t>()/1000-now;
                summary["remaining_seconds"]=std::clamp<std::int64_t>(remaining,-86400,86400);
                valid=!account.account_id.empty() && !account.pet.empty() &&
                    summary["id_matches"]==true && summary["pet_matches"]==true && remaining>5;
            }
        }
    } catch(...) {}
    const auto encoded=summary.dump();
    std::fprintf(stderr,"TF_SESSION:%s\n",encoded.c_str());
    std::fflush(stderr);
    return valid;
}
APPLE_AUTH_CLIENT_EXPORT std::int64_t lab_tf_retry_after(const HttpResponse& response,std::int64_t now) {
    std::int64_t result=-1;
    for(const auto& [name,value]:response.headers) {
        auto key=name;
        std::transform(key.begin(),key.end(),key.begin(),[](unsigned char c){return char(std::tolower(c));});
        if(key!="retry-after")continue;
        try {
            std::int64_t delay=-1;
            if(!value.empty() && value.size()<=18 &&
               value.find_first_not_of("0123456789")==std::string::npos)
                delay=std::stoll(value);
            else {
                const auto when=netdetail::http_date(value);
                if(when>=0)delay=std::max<std::int64_t>(0,when-now);
            }
            result=std::max(result,delay);
        } catch(...) {}
    }
    return result;
}
}
