
enable_testing()
add_executable(tf_sdk_contract tf_sdk_contract.cpp)
target_link_libraries(tf_sdk_contract PRIVATE apple_auth::client)
apple_auth_warnings(tf_sdk_contract)
add_test(NAME tf_sdk_synthetic_contract COMMAND tf_sdk_contract)
