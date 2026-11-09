#include "client/client_internal.hpp"
namespace apple_auth {
APPLE_AUTH_CLIENT_EXPORT Transport lab_tf_curl_transport() {
    return netdetail::make_curl_transport();
}
}
