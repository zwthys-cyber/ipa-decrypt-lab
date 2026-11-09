#include "client/client_internal.hpp"
#include "crypto/backend.hpp"
#include <mbedtls/gcm.h>
#include <algorithm>
namespace apple_auth::netdetail {
DeveloperSession exchange_pet_session(const AccountSession&,const std::function<Headers()>&,
    const Transport&,const std::function<std::int64_t()>&);
}
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT int lab_tf_pet_contract() {
    using namespace netdetail;
    try {
        const std::string application="com.apple.gs.idms.pet";
        const std::int64_t now=1700000000;
        const Bytes key(32,1);
        Json root={{"adsid","SYNTHETIC"},{"status-code",200},{"sk",Json::binary(key)},
            {"c",Json::binary(Bytes(8,2))},{"GsIdmsToken","SYNTHETIC_ROOT"},
            {"t",{{application,{{"token","EXPIRED_SYNTHETIC"},{"expiry",(now-10)*1000}}}}}};
        const auto account=AccountSession::from_plist(encode_plist(root));
        bool requested=false;bool tamper=false;
        Transport server=[&](const HttpRequest& request)->HttpResponse {
            const auto fields=parse_plist(request.body).at("Request");
            if(fields.at("o")!="apptokens" || fields.at("app")!=Json::array({application}) ||
               request.headers.at("X-Apple-App-Info")!=application)throw std::runtime_error("wrong scope");
            const auto expected=hmac_sha256(key,bytes("apptokens"+account.account_id+application));
            if(Bytes(fields.at("checksum").get_binary().begin(),fields.at("checksum").get_binary().end())!=expected)throw std::runtime_error("bad checksum");
            requested=true;
            const auto clear=encode_plist(Json{{"status-code",200},
                {"t",{{application,{{"token","FRESH_SYNTHETIC"},{"expiry",(now+300)*1000}}}}}});
            Bytes encrypted(35+clear.size(),0);
            std::copy_n("XYZ",3,encrypted.begin());
            crypto::Context<mbedtls_gcm_context,mbedtls_gcm_init,mbedtls_gcm_free> cipher;
            if(mbedtls_gcm_setkey(cipher.get(),MBEDTLS_CIPHER_ID_AES,key.data(),256)!=0)throw std::runtime_error("key");
            if(mbedtls_gcm_crypt_and_tag(cipher.get(),MBEDTLS_GCM_ENCRYPT,clear.size(),
                encrypted.data()+3,16,encrypted.data(),3,clear.data(),encrypted.data()+19,
                16,encrypted.data()+encrypted.size()-16)!=0)throw std::runtime_error("encrypt");
            if(tamper)encrypted.back()^=1;
            return {200,encode_plist(Json{{"Response",{{"Status",{{"ec",0}}},{"et",Json::binary(encrypted)}}}}),{}};
        };
        auto headers=[](){return Headers{{"X-Apple-I-MD","SYNTHETIC"},{"X-Apple-I-MD-M","SYNTHETIC"},
            {"X-Apple-I-MD-LU","SYNTHETIC"},{"X-Apple-I-MD-RINFO","1"},
            {"X-Mme-Device-Id","SYNTHETIC"},{"X-MMe-Client-Info","SYNTHETIC"}};};
        const auto grant=exchange_pet_session(account,headers,server,[now](){return now;});
        if(!requested || grant.token!="FRESH_SYNTHETIC" || grant.expires_at_ms!=(now+300)*1000)return 2;
        tamper=true;bool rejected=false;
        try{(void)exchange_pet_session(account,headers,server,[now](){return now;});}
        catch(const std::exception& error){rejected=std::string(error.what())=="Application-token authentication failed";}
        return rejected ? 0 : 2;
    }catch(...){return 2;}
}
}
