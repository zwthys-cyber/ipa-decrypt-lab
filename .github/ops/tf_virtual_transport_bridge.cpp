#include "testflight/internal.hpp"
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

#include <ctime>
namespace apple_auth::netdetail {
DeveloperSession exchange_pet_session(const AccountSession&,const std::function<Headers()>&,
    const Transport&,const std::function<std::int64_t()>&);
}
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT AccountSession lab_tf_refresh_pet(Client& client,const AccountSession& account,const Transport& transport) {
    const auto grant=netdetail::exchange_pet_session(account,[&client](){return client.headers();},
        transport,[](){return std::int64_t(std::time(nullptr));});
    auto value=netdetail::parse_plist(account.plist);
    value["t"]["com.apple.gs.idms.pet"]["token"]=grant.token;
    value["t"]["com.apple.gs.idms.pet"]["expiry"]=grant.expires_at_ms;
    return AccountSession::from_plist(netdetail::encode_plist(value));
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT std::string lab_tf_store_shape(const HttpResponse& response) {
    using netdetail::Json;
    constexpr std::size_t limit=16u<<20;
    Json out={{"body_bytes",std::min(response.body.size(),limit+1)},{"format","other"},
        {"content_type","missing"},{"content_encoding","missing"},{"parsed",false},{"object",false},
        {"status_kind","absent"},{"status_zero",false},{"status_code",0},{"status_in_range",false},
        {"person_id_present",false},{"password_token_present",false},{"failure_present",false},
        {"error_code_present",false},{"message_present",false},{"dialog_present",false},{"parse_failure","none"}};
    auto lower=[](std::string value) {
        std::transform(value.begin(),value.end(),value.begin(),[](unsigned char c){return char(std::tolower(c));});
        return value;
    };
    for(const auto& [key,value]:response.headers) {
        const auto name=lower(key);
        if(name!="content-type" && name!="content-encoding")continue;
        const auto text=value.size()<=512 ? lower(value) : std::string();
        if(name=="content-type") {
            out["content_type"]=text.find("html")!=std::string::npos ? "html" :
                text.find("plist")!=std::string::npos ? "plist" :
                text.find("json")!=std::string::npos ? "json" :
                text.find("octet-stream")!=std::string::npos ? "binary" : "other";
        } else out["content_encoding"]=text=="gzip" || text=="deflate" || text=="br" ? text : "other";
    }
    try {
        if(response.body.empty()) {out["format"]="empty";out["parse_failure"]="empty";return out.dump();}
        if(response.body.size()>limit) {out["parse_failure"]="oversized";return out.dump();}
        const auto first=std::find_if(response.body.begin(),response.body.end(),[](unsigned char c){return !std::isspace(c);});
        if(first==response.body.end()) {out["format"]="empty";out["parse_failure"]="empty";return out.dump();}
        if(response.body.size()>=2 && response.body[0]==0x1f && response.body[1]==0x8b)out["format"]="gzip";
        else if(*first=='{' || *first=='[')out["format"]="json";
        else if(response.body.size()>=8 && std::equal(response.body.begin(),response.body.begin()+8,"bplist00"))out["format"]="binary_plist";
        else {
            const auto prefix=lower(std::string(first,first+std::min<std::size_t>(512,response.body.end()-first)));
            if(prefix.find("<html")!=std::string::npos || prefix.find("<!doctype html")!=std::string::npos)out["format"]="html";
            else if(*first=='<')out["format"]="xml";
        }
        Json value;
        if(out["format"]=="json")value=Json::parse(response.body);
        else if(*first=='<') {
            const std::string xml(response.body.begin(),response.body.end());
            const auto begin=xml.find("<plist"),end=xml.find("</plist>");
            value=begin!=std::string::npos && end!=std::string::npos && end>begin ?
                netdetail::parse_plist(netdetail::bytes(xml.substr(begin,end+8-begin))) : netdetail::parse_plist(response.body);
        } else value=netdetail::parse_plist(response.body);
        out["parsed"]=true;out["object"]=value.is_object();
        if(value.is_object()) {
            out["person_id_present"]=value.contains("dsPersonId");
            out["password_token_present"]=value.contains("passwordToken");
            out["failure_present"]=value.contains("failureType");
            out["error_code_present"]=value.contains("errorCode");
            out["message_present"]=value.contains("customerMessage");
            out["dialog_present"]=value.contains("dialog");
            if(value.contains("status")) {
                const auto& status=value.at("status");
                out["status_kind"]=status.is_number_integer() ? "integer" : status.is_string() ? "string" :
                    status.is_boolean() ? "boolean" : status.is_number() ? "floating" : "other";
                if(status.is_number_integer()) {
                    const bool bounded=status.is_number_unsigned() ? status.get<std::uint64_t>()<=99999999 :
                        status.get<std::int64_t>()>=-99999999 && status.get<std::int64_t>()<=99999999;
                    if(bounded) {
                        const auto code=status.get<std::int64_t>();
                        out["status_in_range"]=true;out["status_code"]=code;out["status_zero"]=code==0;
                    }
                }
            }
        }
    } catch(const Json::exception&) {out["parse_failure"]="json_error";}
      catch(const std::exception& error) {
        const std::string text=error.what();
        out["parse_failure"]=text.find("Invalid plist")!=std::string::npos ? "invalid_plist" :
            text.find("Unsupported plist")!=std::string::npos ? "unsupported_plist" : "other";
    } catch(...) {out["parse_failure"]="other";}
    return out.dump();
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT void lab_tf_invitation_get(const std::filesystem::path& root,const Transport& transport) {
    using netdetail::Json;
    const auto session=Json::parse(netdetail::read_file(root/"tf-session.json",1024*1024));
    const auto profile=Json::parse(netdetail::read_file(root/"profile.json",4096));
    const auto account=netdetail::parse_plist(netdetail::read_file(root/"account.plist",1024*1024));
    const auto& id=account.at("DsPrsId");
    netdetail::require(session.at("udid")==profile.at("hardware20") &&
        session.at("dsid")== (id.is_string() ? id.get<std::string>() : id.dump()),"Saved TestFlight binding mismatch");
    tfdetail::Engine engine(session,transport);
    const auto info=engine.invitation_info();
    netdetail::write_private(root/"invitation.json",netdetail::bytes(info.dump(2)));
}
APPLE_AUTH_CLIENT_EXPORT int lab_tf_invitation_contract() {
    using netdetail::Json;
    try {
        unsigned calls=0;
        Json context={{"accountId","PUBLIC_FIXTURE"},{"sessionId","SYNTHETIC"},{"dsid","12345"},
            {"udid",std::string(40,'a')},{"deviceModel","Mac14,7"},
            {"headers",{{"X-Apple-AMD-M","SYNTHETIC"},{"X-Apple-Store-Front","143441-1,29"}}}};
        Transport fixture=[&calls](const HttpRequest& request)->HttpResponse {
            ++calls;
            netdetail::require(request.method=="GET" && request.body.empty() &&
                request.url=="https://testflight.apple.com/v3/accounts/PUBLIC_FIXTURE/ru/yoNuHexZ" &&
                request.headers.at("X-Session-Id")=="SYNTHETIC" && !request.headers.at("X-Session-Digest").empty(),
                "Fixed invitation GET contract failed");
            return {200,netdetail::bytes("{\"data\":{\"fixture\":true}}"),{}};
        };
        tfdetail::Engine engine(context,fixture);
        const auto result=engine.invitation_info();
        return calls==1 && result.at("fixture")==true ? 0 : 2;
    }catch(...){return 2;}
}
}
