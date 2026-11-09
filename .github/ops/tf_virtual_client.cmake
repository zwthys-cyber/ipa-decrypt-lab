
add_executable(tf_virtual_client tf_virtual_client.cpp)
target_link_libraries(tf_virtual_client PRIVATE apple_auth::client nlohmann_json::nlohmann_json)
apple_auth_warnings(tf_virtual_client)
add_test(NAME tf_virtual_identity_roundtrip COMMAND tf_virtual_client --self-test)
