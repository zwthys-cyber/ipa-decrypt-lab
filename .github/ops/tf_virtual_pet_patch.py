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
    return source.replace(old,new)
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
