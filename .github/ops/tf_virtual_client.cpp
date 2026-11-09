#include <apple_auth/client.hpp>
#include <apple_auth/testflight.hpp>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
#include <ctime>
namespace apple_auth { APPLE_AUTH_CLIENT_EXPORT Transport lab_tf_curl_transport(); APPLE_AUTH_CLIENT_EXPORT int lab_tf_auth_contract(); }
#include <sys/stat.h>
using namespace apple_auth;
using Json=nlohmann::json;
namespace {
struct VerificationNeeded {};
void require(bool ok) { if(!ok) throw std::runtime_error("invalid input"); }
Json read_profile(const std::filesystem::path& root) {
    struct stat info{};
    require(lstat(root.c_str(),&info)==0 && S_ISDIR(info.st_mode) && !(info.st_mode&077));
    std::ifstream file(root/"profile.json");
    Json profile;file>>profile;
    require(profile.at("schema")=="testflight-virtual-profile-v1" &&
            profile.at("origin")=="independent_sdk_virtual_identity");
    return profile;
}
Bytes hardware(const Json& profile) {
    const auto text=profile.at("hardware20").get<std::string>();
    require(std::regex_match(text,std::regex("[a-f0-9]{40}")));
    Bytes result;
    for(std::size_t i=0;i<text.size();i+=2)
        result.push_back(static_cast<std::uint8_t>(std::stoul(text.substr(i,2),nullptr,16)));
    return result;
}
std::string request_stage(const HttpRequest& request) {
    if(request.url.find("/grandslam/GsService2/lookup")!=std::string::npos)return "gsa_lookup";
    if(request.method=="POST" && request.url.find("/grandslam/GsService2")!=std::string::npos) {
        const std::string body(request.body.begin(),request.body.end());
        if(body.find("<string>init</string>")!=std::string::npos)return "gsa_srp_init";
        if(body.find("<string>complete</string>")!=std::string::npos)return "gsa_srp_complete";
        return "gsa_service";
    }
    return "other_apple";
}
void classify(const std::exception& error,Json& report) {
    const std::string text=error.what();
    if(text.size()>32768) { report["failure_category"]="unclassified_exception";return; }
    std::smatch match;
    if(std::regex_search(text,match,std::regex("HTTP ([1-5][0-9]{2})")))
        report["http_status"]=std::stoi(match[1]);
    if(std::regex_search(text,match,std::regex("code (-?[0-9]{1,8})")))
        report["apple_error_code"]=std::stoi(match[1]);
    std::string category="unclassified_exception";
    for(const auto& item:std::vector<std::pair<std::string,std::string>>{
        {"Apple did not confirm the 2FA code","verification_response_unconfirmed"},
        {"Apple requested verification again after 2FA","verification_repeated"},
        {"SrpHandshake server proof is invalid","server_proof_invalid"},
        {"Apple authentication rejected","apple_authentication_rejected"},
        {"GrandSlam session rejected","account_session_rejected"},
        {"usable account token","account_token_missing"},
        {"json.exception","response_schema_invalid"},
        {"GrandSlam missing","response_schema_invalid"},
        {"timed out","transport_timeout"},{"timeout","transport_timeout"},
        {"resolve","transport_error"},{"curl","transport_error"},
        {"HTTP ","http_response_error"}}) {
        if(text.find(item.first)!=std::string::npos) { category=item.second;break; }
    }
    report["failure_category"]=category;
}
int self_test() {
    unsigned calls=0;
    ClientOptions options;options.device_platform=DevicePlatform::mac;
    options.transport=[&calls](const HttpRequest&) -> HttpResponse {
        ++calls;throw std::runtime_error("network forbidden");
    };
    Client original(options);
    const auto state=original.serialize_state();
    Client resumed(ByteView(state),options);
    require(resumed.device_platform()==DevicePlatform::mac &&
            original.mac_device()==resumed.mac_device() &&
            original.serialize_state()==resumed.serialize_state() && calls==0);
    const Bytes key(32,0x5a);
    const auto ciphertext=original.serialize_state(ByteView(key));
    require(ciphertext!=state);
    Client decrypted(ByteView(ciphertext),options,ByteView(key));
    require(decrypted.serialize_state()==state);
    bool wrongKeyRejected=false;
    const Bytes wrongKey(32,0x5b);
    try { Client wrong(ByteView(ciphertext),options,ByteView(wrongKey)); }
    catch(const std::exception&) { wrongKeyRejected=true; }
    require(wrongKeyRejected && calls==0);
    ClientOptions other=options;other.device_platform=DevicePlatform::windows;
    bool rejected=false;
    try { Client mismatch(ByteView(state),other); }
    catch(const std::exception&) { rejected=true; }
    require(rejected && calls==0);
    const std::string synthetic="<plist><key>o</key><string>init</string></plist>";
    require(request_stage({"https://gsa.apple.com/grandslam/GsService2","POST",{},
            Bytes(synthetic.begin(),synthetic.end())})=="gsa_srp_init");
    require(request_stage({"https://gsa.apple.com/grandslam/GsService2/lookup","GET",{}, {}})=="gsa_lookup");
    Json diagnostic={{"http_status",0},{"apple_error_code",0}};
    classify(std::runtime_error("GrandSlam HTTP 503 PRIVATE_ACCOUNT"),diagnostic);
    require(diagnostic["http_status"]==503 && diagnostic["failure_category"]=="http_response_error" &&
            diagnostic.dump().find("PRIVATE_ACCOUNT")==std::string::npos);
    classify(std::runtime_error("Apple authentication rejected (code -22406)"),diagnostic);
    require(diagnostic["apple_error_code"]==-22406 &&
            diagnostic["failure_category"]=="apple_authentication_rejected");
    return 0;
}
}
int main(int argc,char **argv) {
    Json report={{"schema","testflight-virtual-auth-v1"},{"stage","initialization"},
        {"status","failed"},{"virtual_identity",true},{"account_login_attempted",false},
        {"gsa_authenticated",false},{"mac_store_authenticated",false},
        {"tf_authenticated",false},{"catalog_received",false},{"verification_requested",false},
        {"http_status",0},{"sdk_error_code",0},{"apple_error_code",0},{"failure_category","none"},{"last_request_stage","none"}};
    try {
        if(argc==2 && std::string(argv[1])=="--self-test")return self_test();
        if(argc==2 && std::string(argv[1])=="--auth-self-test")return lab_tf_auth_contract();
        require(argc==3 && (std::string(argv[1])=="--authenticate" || std::string(argv[1])=="--prepare-lookup" || std::string(argv[1])=="--lookup"));
        const char *actions=std::getenv("GITHUB_ACTIONS");
        require(actions && std::string(actions)=="true");
        const std::filesystem::path root=argv[2];
        const auto profile=read_profile(root);
        const auto hw=hardware(profile);
        ClientOptions options;options.device_platform=DevicePlatform::mac;
        auto base=lab_tf_curl_transport();
        options.transport=[base,&report](const HttpRequest& request) -> HttpResponse {
            const auto stage=request_stage(request);
            report["last_request_stage"]=stage;report["http_status"]=0;
            if(stage=="gsa_srp_init" || stage=="gsa_srp_complete" || stage=="gsa_service")
                report["account_login_attempted"]=true;
            const auto response=base(request);report["http_status"]=response.status;
            return response;
        };
        Client client(root/"sdk",options);
        report["stage"]="grandslam_provisioning";
        client.provision();
        const std::string command=argv[1];
        if(command=="--prepare-lookup" || command=="--lookup") {
            auto headers=client.headers();
            const auto seconds=std::time(nullptr);
            std::tm utc{};gmtime_r(&seconds,&utc);
            char timestamp[32]{};
            require(std::strftime(timestamp,sizeof(timestamp),"%Y-%m-%dT%H:%M:%SZ",&utc)>0);
            headers["X-Apple-I-Client-Time"]=timestamp;
            headers["Content-Type"]="text/x-xml-plist";headers["Accept"]="*/*";
            if(!headers.contains("User-Agent"))headers["User-Agent"]="iCloud/7.4";
            if(command=="--prepare-lookup") {
                std::ofstream file(root/"lookup-headers.json",std::ios::binary);
                file<<Json(headers).dump();file.close();require(bool(file));
                report["stage"]="gsa_lookup";report["status"]="lookup_prepared";
            } else {
                report["stage"]="gsa_lookup";report["last_request_stage"]="gsa_lookup";
                auto transport=lab_tf_curl_transport();
                const auto response=transport({"https://gsa.apple.com/grandslam/GsService2/lookup","GET",headers,{}});
                report["http_status"]=response.status;report["status"]="lookup_response_received";
            }
            std::cout<<report.dump()<<'\n';
            return 0;
        }
        std::string email,password;
        require(bool(std::getline(std::cin,email)) && bool(std::getline(std::cin,password)) &&
                !email.empty() && !password.empty() && email.size()<320 && password.size()<2048);
        report["stage"]="grandslam_login";
        bool verificationUsed=false;
        const auto account=client.login(email,password,[&]() -> std::string {
            report["verification_requested"]=true;
            const char *live=std::getenv("TF_VIRTUAL_LIVE_OTP");
            if(!live || std::string(live)!="1" || verificationUsed)throw VerificationNeeded{};
            verificationUsed=true;
            std::cerr<<"TF_VIRTUAL_OTP:waiting"<<std::endl;
            std::string code;
            if(!std::getline(std::cin,code) || !std::regex_match(code,std::regex("[0-9]{6}")))
                throw VerificationNeeded{};
            return code;
        });
        report["gsa_authenticated"]=true;
        account.save(root/"account.plist");
        client.set_session_data(account.plist);
        report["stage"]="mac_store_login";
        const auto store=client.login_store_with_pet(email,account);
        report["mac_store_authenticated"]=true;
        store.save(root/"mac-store.plist");
        client.set_session_data(store.plist(),SessionKind::store);
        const auto model=client.mac_device().model;
        Headers headers={{"User-Agent","IPADecryptLab-TestFlight/0.2 (independent virtual Mac)"},
            {"X-Apple-Device-Model",model},{"X-Apple-TA-Device",model},
            {"X-Apple-TestFlight-iOS","0"},{"X-Apple-Rosetta-Available","0"}};
        report["stage"]="testflight_session";
        auto tf=TestFlightClient::from_store_session(store,hw,headers);
        report["tf_authenticated"]=true;
        tf.save(root/"tf-session.json");
        report["stage"]="testflight_catalog";
        tf.save_catalog(root/"catalog.json");
        report["catalog_received"]=true;report["status"]="catalog_verified";
    } catch(const VerificationNeeded&) {
        report["status"]="verification_required";report["verification_requested"]=true;
        report["failure_category"]="verification_required";
    } catch(const Error& error) {
        report["sdk_error_code"]=static_cast<int>(error.code());
        classify(error,report);
    } catch(const std::exception& error) {
        classify(error,report);
    } catch(...) { report["failure_category"]="nonstandard_exception"; }
    std::cout<<report.dump()<<'\n';
    return report["status"]=="catalog_verified" ? 0 : 2;
}
