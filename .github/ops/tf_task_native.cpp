#include "testflight/internal.hpp"
#include <regex>
#include <ctime>
#include <fcntl.h>
#include <unistd.h>
namespace apple_auth {
using netdetail::Json;
namespace {
std::string scalar(const Json& value) {
    netdetail::require(value.is_string() || value.is_number_integer(),"Invalid TF target scalar");
    return value.is_string()?value.get<std::string>():value.dump();
}
bool agreement(const Json& value,unsigned depth=0) {
    netdetail::require(depth<64,"TF response depth exceeded");
    if(value.is_object()) {
        for(const auto* field:{"requiresAgreement","termsAccepted","isBetaAgreementAccepted"}) {
            if(value.contains(field) && value.at(field).is_boolean() &&
                value.at(field).get<bool>()==(std::string(field)=="requiresAgreement"))return true;
        }
    }
    if(value.is_structured())for(const auto& child:value)
        if(child.is_structured() && agreement(child,depth+1))return true;
    return false;
}
Json bound_context(const std::filesystem::path& root) {
    const auto context=Json::parse(netdetail::read_file(root/"tf-session.json",1024*1024));
    const auto profile=Json::parse(netdetail::read_file(root/"profile.json",8192));
    const auto account=netdetail::parse_plist(netdetail::read_file(root/"account.plist",1024*1024));
    netdetail::require(profile.at("schema")=="testflight-virtual-profile-v1" &&
        profile.at("origin")=="independent_sdk_virtual_identity" &&
        context.at("udid")==profile.at("hardware20") &&
        context.at("dsid")==scalar(account.at("DsPrsId")) &&
        std::regex_match(context.at("deviceModel").get<std::string>(),std::regex("(Mac|MacBook|Macmini|MacPro|iMac)[A-Za-z0-9,.-]{1,100}")),
        "Saved TF task identity mismatch");
    return context;
}
Json task_request(const std::filesystem::path& path) {
    const auto request=Json::parse(netdetail::read_file(path,4096));
    const auto run=std::getenv("GITHUB_RUN_ID"),source=std::getenv("GITHUB_SHA"),attempt=std::getenv("GITHUB_RUN_ATTEMPT");
    netdetail::require(run && source && attempt && std::string(attempt)=="1" &&
        request.at("schema")=="tf-worker-request-v1" && request.at("run_id")==run &&
        request.at("source_commit")==source && std::regex_match(request.at("invite").get<std::string>(),std::regex("[A-Za-z0-9_-]{6,80}")) &&
        std::regex_match(request.at("request_id").get<std::string>(),std::regex("tf_[a-f0-9]{32}")),"Invalid TF task request");
    return request;
}
bool member(tfdetail::Engine& engine,const std::string& bundle,const std::string& app) {
    try{return engine.invitation_app_binding(bundle)==app;}
    catch(const std::exception& error) {
        if(std::string(error.what())=="Application is absent from the iOS TestFlight catalog")return false;
        throw;
    }
}
}
APPLE_AUTH_CLIENT_EXPORT std::string lab_tf_task(const std::string& mode,const std::filesystem::path& root,
        const std::filesystem::path& request_path,const std::filesystem::path& output) {
    Json report={{"schema","tf-task-native-v1"},{"status","failed"},{"http_status",0},{"membership_verified",false},
        {"invitation_open",false},{"agreement_required",false},{"downloaded",false},{"transport_mode","unknown"},
        {"archive_members",0},{"encrypted_images",0},{"clear_images",0},{"downloaded_bytes",0},{"output_bytes",0}};
    auto base=netdetail::make_curl_transport();
    Transport transport=[&](const HttpRequest& request)->HttpResponse {
        report["http_status"]=0;auto response=base(request);report["http_status"]=response.status;
        netdetail::require(response.body.size()<=16*1024*1024,"TF response size exceeded");
        return response;
    };
    try {
        const auto request=task_request(request_path),context=bound_context(root);
        const auto code=request.at("invite").get<std::string>();
        tfdetail::Engine engine(context,transport);
        if(mode=="accept") {
            const auto permit=Json::parse(netdetail::read_file(root/"accept-permit.json",8192));
            netdetail::require(permit.at("schema")=="tf-accept-permit-v1" && permit.at("permitted")==true &&
                permit.at("invite")==request.at("invite") && permit.at("request_id")==request.at("request_id") &&
                permit.at("run_id")==request.at("run_id") && permit.at("source_commit")==request.at("source_commit") &&
                permit.at("expires").is_number_integer() && permit.at("expires").get<std::int64_t>()>std::time(nullptr) &&
                std::regex_match(permit.at("nonce").get<std::string>(),std::regex("[a-f0-9]{32}")),"TF acceptance permit mismatch");
            const auto marker=root/"accept-native-sent";
            const auto fd=::open(marker.c_str(),O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW,0600);
            netdetail::require(fd>=0,"TF acceptance already attempted");
            ::close(fd);
            const auto response=engine.task_invitation_accept(code);
            netdetail::write_private(root/"accept-response.json",netdetail::bytes(response.dump()));
            report["status"]="acceptance_response_received";
        } else if(mode=="inspect" || mode=="download") {
            const auto info=engine.task_invitation_info(code);
            netdetail::write_private(root/"invitation.json",netdetail::bytes(info.dump()));
            netdetail::require(info.is_object() && info.contains("app") && info.at("app").is_object(),"TF invitation unavailable");
            const auto& app=info.at("app");
            const auto bundle=app.at("bundleId").get<std::string>(),identifier=scalar(app.at("appAdamId"));
            netdetail::require(std::regex_match(bundle,std::regex("[A-Za-z0-9][A-Za-z0-9.-]{1,254}")) &&
                std::regex_match(identifier,std::regex("[1-9][0-9]{0,19}")),"TF target binding invalid");
            report["agreement_required"]=agreement(info);
            report["invitation_open"]=info.value("status","")=="OPEN";
            const bool enrolled=member(engine,bundle,identifier);report["membership_verified"]=enrolled;
            if(mode=="inspect") {
                report["status"]=enrolled?"membership_verified":
                    report["invitation_open"]==true && report["agreement_required"]==false?"invitation_available":"invitation_unavailable";
            } else {
                netdetail::require(enrolled && report["agreement_required"]==false,"TF membership not verified");
                auto client=TestFlightClient::load(root/"tf-session.json",std::nullopt,transport);
                const auto downloaded=client.download(bundle,output/"beta.ipa",true);
                const auto metadata=Json::parse(netdetail::read_file(downloaded.artifacts/"install-metadata.json",16*1024*1024));
                report["transport_mode"]=metadata.at("dpInfo").is_null()?"plain_zip":"encrypted";
                report["archive_members"]=downloaded.archive.members;report["encrypted_images"]=downloaded.archive.encrypted_images;
                report["clear_images"]=downloaded.archive.clear_images;report["downloaded_bytes"]=downloaded.downloaded_bytes;
                report["output_bytes"]=std::filesystem::file_size(output/"beta.ipa");
                report["downloaded"]=true;report["status"]="beta_downloaded";
            }
        } else throw std::runtime_error("Invalid TF task mode");
    }catch(const std::exception& error) {
        const std::string text=error.what();
        if(text.size()<=32768)netdetail::write_private(root/"task-failure.txt",netdetail::bytes(text));
        if(report["http_status"]==401 || report["http_status"]==403)report["status"]="session_requires_maintenance";
        else if(report["http_status"]==429)report["status"]="rate_limited";
    }catch(...){}
    return report.dump();
}
APPLE_AUTH_CLIENT_EXPORT int lab_tf_task_contract() {
    try {
        unsigned calls=0;
        Json context={{"accountId","PUBLIC_FIXTURE"},{"sessionId","SYNTHETIC"},{"dsid","12345"},
            {"udid",std::string(40,'a')},{"deviceModel","Mac14,7"},
            {"headers",{{"X-Apple-AMD-M","SYNTHETIC"},{"X-Apple-Store-Front","143465-1,29"}}}};
        bool accept=false,fail=false;
        Transport fixture=[&](const HttpRequest& request)->HttpResponse {
            ++calls;
            netdetail::require(request.url=="https://testflight.apple.com/v3/accounts/PUBLIC_FIXTURE/ru/SYNTH123"+std::string(accept?"/accept":"") &&
                request.method==(accept?"POST":"GET") && request.body.empty(),"TF task endpoint escaped");
            return {fail?503:200,netdetail::bytes("{\"data\":{\"fixture\":true}}"),{}};
        };
        tfdetail::Engine engine(context,fixture);
        netdetail::require(engine.task_invitation_info("SYNTH123").at("fixture")==true && calls==1,"TF read contract failed");
        accept=true;calls=0;netdetail::require(engine.task_invitation_accept("SYNTH123").at("fixture")==true && calls==1,"TF post contract failed");
        fail=true;calls=0;bool rejected=false;
        try{(void)engine.task_invitation_accept("SYNTH123");}catch(...){rejected=true;}
        netdetail::require(rejected && calls==1,"TF post retried");
        calls=0;rejected=false;
        try{(void)engine.task_invitation_info("../PRIVATE");}catch(...){rejected=true;}
        netdetail::require(rejected && calls==0 && agreement(Json{{"requiresAgreement",true}}) &&
            agreement(Json{{"termsAccepted",false}}) && !agreement(Json{{"termsAccepted",true}}),"TF unsafe invitation accepted");
        return 0;
    }catch(...){return 2;}
}
}
