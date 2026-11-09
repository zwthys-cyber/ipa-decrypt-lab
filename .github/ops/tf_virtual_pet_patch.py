"""Fixed-target PET renewal plus credential-free Mac Store signing prewarm."""
import hashlib
from pathlib import Path
import sys
STORE_BLOB="1995b03afe17497cf63e554b67438b257fce542d"
def patch_auth(source):
    start=source.index("DeveloperSession exchange_developer_session(")
    end=source.index("\n} // namespace apple_auth::netdetail",start)
    original=source[start:end].rstrip()
    if "exchange_pet_session" in source or original.count('"com.apple.gs.xcode.auth"')!=1:
        raise ValueError("tf_pet_auth_anchor_invalid")
    copied=original.replace("exchange_developer_session(","exchange_pet_session(",1)
    copied=copied.replace('"com.apple.gs.xcode.auth"','"com.apple.gs.idms.pet"')
    copied=copied.replace("    apply_xcode_headers(headers);",'    headers["X-Apple-App-Info"] = application;')
    copied=copied.replace('    const auto& token = decoded.at("t").at(application);',
        '    require(decoded.contains("status-code") && decoded.at("status-code").is_number_integer() &&\n'
        '                decoded.at("status-code").get<std::int64_t>() == 200, "PET refresh was not confirmed");\n'
        '    const auto& token = decoded.at("t").at(application);')
    copied=copied.replace('require(expiry >= 0 && (!expiry || clock() < expiry / 1000), "Developer Session has expired");',
        'require(expiry > 0 && clock() + 5 < expiry / 1000, "Refreshed PET has expired");')
    copied=copied.replace("Developer Session HTTP ","PET refresh HTTP ")
    if copied.count('constexpr const char* application = "com.apple.gs.idms.pet";')!=1 or 'Refreshed PET has expired' not in copied or 'apply_xcode_headers(headers);' in copied:
        raise ValueError("tf_pet_patch_incomplete")
    return source[:end]+"\n\n"+copied+"\n"+source[end:]

def patch_store(raw):
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!=STORE_BLOB:
        raise ValueError("tf_store_source_mismatch")
    old="void StoreClient::provision() {\n    impl_->provision();\n}"
    new="void StoreClient::provision() {\n    impl_->provision();\n    if (impl_->protocol == StoreProtocol::macos_accounts) impl_->prepare_sap();\n}"
    source=raw.decode()
    if source.count(old)!=1:raise ValueError("tf_store_anchor_invalid")
    source=source.replace(old,new)
    end=source.rindex("\n} // namespace apple_auth")
    helper=r"""
namespace {
Json lab_cookie_flags(const Json& cookies) {
    Json flags={{"count",cookies.size()},{"name_bad",0},{"value_bad",0},{"domain_bad",0},
        {"path_bad",0},{"expiry_kind_bad",0},{"host_flag_kind_bad",0}};
    for(const auto& c:cookies) {
        const auto name=c.at("name").get<std::string>(),value=c.at("value").get<std::string>();
        const auto domain=c.at("domain").get<std::string>(),path=c.at("path").get<std::string>();
        if(name.empty() || name.find_first_of("=; ,")!=std::string::npos)flags["name_bad"]=flags["name_bad"].get<int>()+1;
        if(value.find(';')!=std::string::npos)flags["value_bad"]=flags["value_bad"].get<int>()+1;
        if(domain!="apple.com" && !domain.ends_with(".apple.com"))flags["domain_bad"]=flags["domain_bad"].get<int>()+1;
        if(!path.starts_with('/'))flags["path_bad"]=flags["path_bad"].get<int>()+1;
        if(!c.at("expires").is_number_integer())flags["expiry_kind_bad"]=flags["expiry_kind_bad"].get<int>()+1;
        if(!c.at("host_only").is_boolean())flags["host_flag_kind_bad"]=flags["host_flag_kind_bad"].get<int>()+1;
    }
    return flags;
}
}
APPLE_AUTH_CLIENT_EXPORT int lab_tf_cookie_contract() {
    try {
        const Json cookies=Json::array({Json{{"name","fixture"},{"value","SYNTHETIC"},{"domain","apple.com"},
            {"path","/"},{"expires",std::int64_t(1800000000)},{"host_only",false}}});
        const auto after=parse_plist(encode_plist(cookies));
        require(lab_cookie_flags(cookies)==lab_cookie_flags(after),"Cookie roundtrip changed types");
        const Json state={{"kind","apple-auth-store"},{"version",1},{"protocol","macos-accounts"},
            {"account",{{"dsPersonId","12345"},{"passwordToken","SYNTHETIC_TOKEN"}}},
            {"storefront","143441-1,29"},{"guid","AABBCCDDEEFF"},{"cookies",cookies}};
        const auto accepted=StoreSession::from_plist(encode_plist(state));
        require(accepted.account_id()=="12345","Cookie fixture account mismatch");
        auto bad=state;bad["cookies"][0]["domain"]="invalid.example";
        bool rejected=false;
        try{(void)StoreSession::from_plist(encode_plist(bad));}catch(const std::exception&){rejected=true;}
        require(rejected,"Cookie foreign-domain guard missing");
        return 0;
    }catch(...){return 2;}
}
APPLE_AUTH_CLIENT_EXPORT std::string lab_tf_cookie_inspect(const Path& root) {
    const auto meta=Json::parse(read_file(root/"store-auth-meta.json",128*1024));
    const auto raw=read_file(root/"store-auth-response.bin",16u<<20);
    const auto response=HttpResponse{meta.at("status").get<int>(),raw,meta.at("response_headers").get<std::vector<std::pair<std::string,std::string>>>()};
    const auto requestHeaders=meta.at("request_headers").get<Headers>();
    const auto url=meta.at("url").get<std::string>();
    const auto result=decode_store(raw);
    require(response.status==200 && result.value("status",Json())==0 &&
        requestHeaders.contains("X-DSID") && scalar(result.at("dsPersonId"))==requestHeaders.at("X-DSID") &&
        result.at("passwordToken").is_string(),"Captured Store response binding failed");
    Json cookies=Json::array();
    cookies_update(cookies,url,response,1794252273);
    const auto after=parse_plist(encode_plist(cookies));
    const auto failure=str(read_file(root/"failure.txt",32768));
    return Json{{"schema","tf-cookie-inspection-v1"},{"before",lab_cookie_flags(cookies)},
        {"after",lab_cookie_flags(after)},{"original_failure",
            failure=="Invalid saved Store cookie" ? "invalid_saved_cookie" :
            failure=="Invalid Store cookies" ? "invalid_cookie_container" : "other"},
        {"response_binding",true},{"network_requests",0}}.dump();
}
"""
    return source[:end]+"\n"+helper+"\n"+source[end:]
def patch_client(raw):
    if hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()!="0487dcad3a8e0e8d9e80a393f5495d030245b594":
        raise ValueError("tf_client_source_mismatch")
    old="    impl_->store_client().provision();"
    new="    impl_->store_client(device_platform() == DevicePlatform::mac ? StoreProtocol::macos_accounts : StoreProtocol::android_music).provision();"
    source=raw.decode()
    if source.count(old)!=1:raise ValueError("tf_client_anchor_invalid")
    return source.replace(old,new)
if __name__=="__main__":
    auth=Path(sys.argv[1]);store=Path(sys.argv[2])
    auth.write_text(patch_auth(auth.read_text()))
    store.write_text(patch_store(store.read_bytes()))

    client=Path(sys.argv[3]);client.write_text(patch_client(client.read_bytes()))
