#!/usr/bin/env bash
# CI-only fresh runner: fetch verified binaries without compiling the project.
set -euo pipefail
source deploy/managed/circleci/public-build-common.sh
brew update
brew install cmake ninja pkgconf mbedtls@3 curl nlohmann-json libzip
python3 deploy/managed/circleci/test_fetch_runtime.py -v
mkdir -p circle-runtime-dist/consumer
for variant in base cn testflight; do
  python3 deploy/managed/circleci/fetch_runtime.py --variant "$variant" --output "fetched-circle-$variant" | tee "circle-runtime-dist/consumer/$variant.json"
done
test ! -e native-source/ApplePackage/.build
test ! -e tf-sdk-build
fetched-circle-base/ApplePackageTool --help
fetched-circle-base/offline-engine --help
fetched-circle-cn/ApplePackageTool login-cn --help
fetched-circle-cn/ApplePackageTool resume-cn --help
fetched-circle-cn/ApplePackageTool summary-cn --help
fetched-circle-testflight/tf_virtual_client --task-self-test
fetched-circle-testflight/tf_virtual_client --plain-transport-self-test
fetched-circle-testflight/tf_virtual_client --cookie-self-test
