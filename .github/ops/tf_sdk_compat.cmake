
# libzip 1.11.4 exposes Clang nullability annotations in its public C header.
# Apply after upstream warning options so -Wpedantic cannot re-enable this group.
# Preserve all other warnings-as-errors, crypto/ZIP guards and upstream sources.
if(APPLE AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  target_compile_options(apple_auth_client PRIVATE
    "$<$<COMPILE_LANGUAGE:CXX>:-Wno-nullability-extension>")
endif()
