#!/usr/bin/env bash
# Standalone public TF producer. No Go or Swift compilation is required here.
set -euo pipefail
source deploy/managed/circleci/public-build-common.sh
# The runner image and current formula metadata can contain different Homebrew generations.
brew --version
brew update
brew --version
checkout_public apple-auth/apple-auth 98c862f7bebc8283a9b87f1578e703f0765dc81d apple-auth
if ! brew install cmake ninja pkgconf mbedtls@3 curl nlohmann-json libzip; then
  # Homebrew can leave bottles installed after a failed dependency post-install.
  # Recover those steps explicitly; any remaining error stops this public build.
  for formula in ca-certificates openssl@4 libssh2; do
    if brew list --versions "$formula" >/dev/null 2>&1; then
      HOMEBREW_DEVELOPER=1 HOMEBREW_STDERR=1 brew postinstall --verbose "$formula"
    fi
  done
  brew install cmake ninja pkgconf mbedtls@3 curl nlohmann-json libzip
fi
python3 -m unittest discover -s .github/ops -p 'test_tf_virtual*.py'
python3 -m unittest discover -s .github/ops -p 'test_tf_invitation.py'
node --test .github/ops/cn_action.test.cjs
python3 .github/ops/tf_virtual_transport_patch.py native-source/apple-auth/src/client/transport.cpp
python3 .github/ops/tf_virtual_auth_patch.py native-source/apple-auth/src/client/authentication.cpp
python3 .github/ops/tf_virtual_pet_patch.py native-source/apple-auth/src/client/authentication.cpp native-source/apple-auth/src/client/store.cpp native-source/apple-auth/src/client/client.cpp native-source/apple-auth/src/client/apple_plist.cpp
python3 .github/ops/tf_virtual_invitation_patch.py native-source/apple-auth/src/testflight/internal.hpp native-source/apple-auth/src/testflight/protocol.cpp
cp .github/ops/tf_virtual_pet_contract.cpp native-source/apple-auth/lab_tf_pet_contract.cpp
cp .github/ops/tf_sdk_contract.cpp native-source/apple-auth/tf_sdk_contract.cpp
cp .github/ops/tf_task_native.cpp native-source/apple-auth/lab_tf_task_native.cpp
cp .github/ops/tf_virtual_client.cpp native-source/apple-auth/tf_virtual_client.cpp
cp .github/ops/tf_virtual_transport_bridge.cpp native-source/apple-auth/lab_tf_transport_bridge.cpp
cp .github/ops/tf_virtual_auth_contract.cpp native-source/apple-auth/lab_tf_auth_contract.cpp
cat .github/ops/tf_sdk_contract.cmake .github/ops/tf_virtual_client.cmake .github/ops/tf_sdk_compat.cmake >> native-source/apple-auth/CMakeLists.txt
tf_prefix="$(brew --prefix mbedtls@3);$(brew --prefix curl);$(brew --prefix nlohmann-json);$(brew --prefix libzip)"
cmake -S native-source/apple-auth -B tf-sdk-build -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$tf_prefix" -DAPPLE_AUTH_WITH_TESTFLIGHT=ON -DAPPLE_AUTH_BUILD_EXAMPLES=ON
cmake --build tf-sdk-build --parallel 4
ctest --test-dir tf-sdk-build --output-on-failure --no-tests=error --timeout 180
python3 deploy/managed/circleci/runtime.py pack-and-verify --variant testflight
mv tf-sdk-build tf-sdk-build-hidden
relocated-circle-testflight-runtime/tf_virtual_client --task-self-test
relocated-circle-testflight-runtime/tf_virtual_client --plain-transport-self-test
relocated-circle-testflight-runtime/tf_virtual_client --cookie-self-test
