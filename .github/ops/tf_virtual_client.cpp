#include <apple_auth/client.hpp>
#include <apple_auth/testflight.hpp>
#include <nlohmann/json.hpp>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <regex>
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
    return 0;
}
}
int main(int argc,char **argv) {
    Json report={{"schema","testflight-virtual-auth-v1"},{"stage","initialization"},
        {"status","failed"},{"virtual_identity",true},{"account_login_attempted",false},
        {"gsa_authenticated",false},{"mac_store_authenticated",false},
        {"tf_authenticated",false},{"catalog_received",false},{"verification_requested",false},
        {"http_status",0},{"sdk_error_code",0}};
    try {
        if(argc==2 && std::string(argv[1])=="--self-test")return self_test();
        require(argc==3 && std::string(argv[1])=="--authenticate");
        const char *actions=std::getenv("GITHUB_ACTIONS");
        require(actions && std::string(actions)=="true");
        const std::filesystem::path root=argv[2];
        const auto profile=read_profile(root);
        const auto hw=hardware(profile);
        std::string email,password;
        require(bool(std::getline(std::cin,email)) && bool(std::getline(std::cin,password)) &&
                !email.empty() && !password.empty() && email.size()<320 && password.size()<2048);
        ClientOptions options;options.device_platform=DevicePlatform::mac;
        Client client(root/"sdk",options);
        report["stage"]="grandslam_provisioning";
        client.provision();
        report["stage"]="grandslam_login";report["account_login_attempted"]=true;
        const auto account=client.login(email,password,[]() -> std::string {
            throw VerificationNeeded{};
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
    } catch(const Error& error) {
        report["sdk_error_code"]=static_cast<int>(error.code());
        const std::string text=error.what();
        std::smatch match;
        if(std::regex_search(text,match,std::regex("HTTP ([1-5][0-9]{2})")))
            report["http_status"]=std::stoi(match[1]);
    } catch(...) {}
    std::cout<<report.dump()<<'\n';
    return report["status"]=="catalog_verified" ? 0 : 2;
}
