#include "client/client_internal.hpp"
#include <algorithm>
#include <cctype>
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT Transport lab_tf_curl_transport() {
    return netdetail::make_curl_transport();
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT bool lab_tf_account_session_valid(const AccountSession& account,std::int64_t now) {
    try {
        const auto value=netdetail::parse_plist(account.plist);
        const auto& pet=value.at("t").at("com.apple.gs.idms.pet");
        return !account.account_id.empty() && !account.pet.empty() &&
            value.at("adsid")==account.account_id && pet.at("token")==account.pet &&
            pet.at("expiry").is_number_integer() &&
            pet.at("expiry").get<std::int64_t>()/1000>now+5;
    } catch(...) { return false; }
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
