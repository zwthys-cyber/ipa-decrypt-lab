#include <regex>
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

namespace apple_auth {
namespace {
netdetail::Json lab_bound_tf_context(const std::filesystem::path& root) {
    using netdetail::Json;
    const auto context=Json::parse(netdetail::read_file(root/"tf-session.json",1024*1024));
    const auto profile=Json::parse(netdetail::read_file(root/"profile.json",4096));
    const auto account=netdetail::parse_plist(netdetail::read_file(root/"account.plist",1024*1024));
    const auto& id=account.at("DsPrsId");
    netdetail::require(context.at("udid")==profile.at("hardware20") &&
        context.at("dsid")==(id.is_string()?id.get<std::string>():id.dump()),"Saved TestFlight binding mismatch");
    return context;
}
}
APPLE_AUTH_CLIENT_EXPORT void lab_tf_invitation_refresh(const std::filesystem::path& root,const Transport& transport) {
    const auto context=lab_bound_tf_context(root);
    tfdetail::Engine engine(context,transport);
    netdetail::write_private(root/"invitation.json",netdetail::bytes(engine.invitation_info().dump(2)));
    netdetail::write_private(root/"catalog.json",netdetail::bytes(engine.catalog().dump(2)));
}
APPLE_AUTH_CLIENT_EXPORT void lab_tf_invitation_accept(const std::filesystem::path& root,const Transport& transport) {
    using netdetail::Json;
    const auto proof=Json::parse(netdetail::read_file(root/"invitation-intent-approved.json",8192));
    const auto run=std::getenv("GITHUB_RUN_ID"),source=std::getenv("GITHUB_SHA"),attempt=std::getenv("GITHUB_RUN_ATTEMPT");
    netdetail::require(run && source && attempt && std::string(attempt)=="1" &&
        proof.at("schema")=="tf-invite-approved-v1" && proof.at("approved")==true &&
        proof.at("worker_run")==run && proof.at("source_commit")==source && proof.at("invite")=="yoNuHexZ" &&
        proof.at("expires").is_number_integer() && proof.at("expires").get<std::int64_t>()>std::time(nullptr),
        "Invitation intent binding failed");
    tfdetail::Engine engine(lab_bound_tf_context(root),transport);
    netdetail::write_private(root/"accept-response.json",netdetail::bytes(engine.invitation_accept().dump(2)));
}
APPLE_AUTH_CLIENT_EXPORT int lab_tf_invitation_post_contract() {
    using netdetail::Json;
    try {
        Json context={{"accountId","PUBLIC_FIXTURE"},{"sessionId","SYNTHETIC"},{"dsid","12345"},
            {"udid",std::string(40,'a')},{"deviceModel","Mac14,7"},
            {"headers",{{"X-Apple-AMD-M","SYNTHETIC"},{"X-Apple-Store-Front","143441-1,29"}}}};
        unsigned calls=0;bool fail=false;
        Transport fixture=[&](const HttpRequest& request)->HttpResponse {
            ++calls;
            netdetail::require(request.method=="POST" && request.body.empty() &&
                request.url=="https://testflight.apple.com/v3/accounts/PUBLIC_FIXTURE/ru/yoNuHexZ/accept" &&
                request.headers.at("X-Session-Id")=="SYNTHETIC","Fixed invitation POST contract failed");
            return {fail?503:200,netdetail::bytes("{\"data\":{\"fixture\":true}}"),{}};
        };
        tfdetail::Engine engine(context,fixture);
        netdetail::require(engine.invitation_accept().at("fixture")==true && calls==1,"POST response contract failed");
        fail=true;calls=0;bool rejected=false;
        try{(void)engine.invitation_accept();}catch(const std::exception&){rejected=true;}
        return rejected && calls==1 ? 0 : 2;
    }catch(...){return 2;}
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT void lab_tf_invitation_bind(const std::filesystem::path& root,const Transport& transport) {
    using netdetail::Json;
    const auto info=Json::parse(netdetail::read_file(root/"invitation.json",1024*1024));
    const auto accepted=Json::parse(netdetail::read_file(root/"accept-response.json",1024*1024));
    const auto& app=info.at("app");
    const auto scalar=[](const Json& item) {
        netdetail::require(item.is_string() || item.is_number_integer(),"Invalid app binding");
        return item.is_string()?item.get<std::string>():item.dump();
    };
    netdetail::require(app.at("name")=="A.I." && accepted.at("bundleId")==app.at("bundleId") &&
        scalar(accepted.at("appAdamId"))==scalar(app.at("appAdamId")),"Accept response target mismatch");
    tfdetail::Engine engine(lab_bound_tf_context(root),transport);
    const auto found=engine.invitation_app_binding(app.at("bundleId").get<std::string>());
    netdetail::require(found==scalar(app.at("appAdamId")),"Catalog detail target mismatch");
}
}

namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT std::string lab_tf_beta_download(const std::filesystem::path& root,const std::filesystem::path& output) {
    using netdetail::Json;
    Json report={{"schema","tf-beta-download-v1"},{"status","failed"},{"stage","target_binding"},
        {"downloaded",false},{"transport_removed",false},{"decryption_proven",false},
        {"archive_members",0},{"encrypted_images",0},{"clear_images",0},{"downloaded_bytes",0},
        {"output_bytes",0},{"http_status",0},{"failure_category","none"}};
    auto base=lab_tf_curl_transport();
    Transport transport=[&](const HttpRequest& request)->HttpResponse {
        report["http_status"]=0;
        const auto response=base(request);report["http_status"]=response.status;return response;
    };
    try {
        lab_tf_invitation_bind(root,transport);
        const auto info=Json::parse(netdetail::read_file(root/"invitation.json",1024*1024));
        const auto bundle=info.at("app").at("bundleId").get<std::string>();
        (void)lab_bound_tf_context(root);
        auto client=TestFlightClient::load(root/"tf-session.json",std::nullopt,transport);
        report["stage"]="download_and_transport";
        const auto result=client.download(bundle,output/"beta.ipa",true);
        std::filesystem::copy_file(result.artifacts/"install-metadata.json",root/"tf-install-metadata.json",
            std::filesystem::copy_options::overwrite_existing);
        std::filesystem::permissions(root/"tf-install-metadata.json",std::filesystem::perms::owner_read|std::filesystem::perms::owner_write);
        report["archive_members"]=result.archive.members;report["encrypted_images"]=result.archive.encrypted_images;
        report["clear_images"]=result.archive.clear_images;report["downloaded_bytes"]=result.downloaded_bytes;
        report["output_bytes"]=std::filesystem::file_size(output/"beta.ipa");
        report["downloaded"]=true;report["transport_removed"]=true;
        report["stage"]="archive_received";report["status"]="beta_downloaded";
    } catch(const std::exception& error) {
        const std::string text=error.what();
        if(text.size()<=32768)netdetail::write_private(root/"download-failure.txt",netdetail::bytes(text));
        std::smatch match;
        if(std::regex_search(text,match,std::regex("HTTP ([1-5][0-9]{2})")))report["http_status"]=std::stoi(match[1]);
        report["failure_category"]=report["http_status"]==429 ? "rate_limited" : "download_or_metadata_failed";
    } catch(...) {report["failure_category"]="nonstandard_exception";}
    return report.dump();
}
}
