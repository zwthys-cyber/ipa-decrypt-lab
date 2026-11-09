
add_executable(tf_virtual_client tf_virtual_client.cpp)
target_link_libraries(tf_virtual_client PRIVATE apple_auth::client nlohmann_json::nlohmann_json)
apple_auth_warnings(tf_virtual_client)
add_test(NAME tf_virtual_identity_roundtrip COMMAND tf_virtual_client --self-test)

target_sources(apple_auth_client PRIVATE lab_tf_transport_bridge.cpp)

target_sources(apple_auth_client PRIVATE lab_tf_auth_contract.cpp)
add_test(NAME tf_virtual_srp_contract COMMAND tf_virtual_client --auth-self-test)

target_sources(apple_auth_client PRIVATE lab_tf_pet_contract.cpp)
add_test(NAME tf_virtual_pet_contract COMMAND tf_virtual_client --pet-self-test)

add_test(NAME tf_virtual_cookie_contract COMMAND tf_virtual_client --cookie-self-test)

add_test(NAME tf_virtual_invitation_get_contract COMMAND tf_virtual_client --invite-self-test)
