#!/usr/bin/env bash
# Public source only. Never mount account credentials in this producer.
set -euo pipefail
source deploy/managed/circleci/public-build-common.sh
checkout_public Lakr233/ApplePackage 391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b ApplePackage
checkout_public DrWhax/unfairplay 26a099fcb2292eaacd9e0ce89793cdbc88e516d1 unfairplay
checkout_public majd/ipatool d9c0247daea564d3ec7d04a9b015d0a29af66b04 ipatool
checkout_public FiloSottile/age b74dce4cdbe35b5e5f66c06d9612b72f89028758 age
if ! command -v go >/dev/null 2>&1; then
  HOMEBREW_NO_AUTO_UPDATE=1 brew install go
fi
command -v go
# Downloaded Go toolchains are authenticated by the Go checksum database.
export GOTOOLCHAIN=go1.27.0
go version
mkdir -p native-source/ipatool/cmd/lab-kbsync
cp tools/kbsync_main.go native-source/ipatool/cmd/lab-kbsync/main.go
cp tests/kbsync_main_test.go native-source/ipatool/cmd/lab-kbsync/main_test.go
(
  cd native-source/ipatool
  go test -p 2 -timeout 180s ./cmd/lab-kbsync
  go build -p 2 -trimpath -o ../../lab-kbsync ./cmd/lab-kbsync
)
(
  cd native-source/unfairplay
  go test -p 2 -timeout 180s ./internal/fairplay ./cmd/unfairplay
  go build -p 2 -trimpath -o ../../offline-engine ./cmd/unfairplay
)
python3 -m unittest discover -s tests -p 'test_*.py' -v
node --test tests/progress_worker.test.cjs
python3 tools/patch_swift_diagnostics.py native-source/ApplePackage
python3 tools/patch_ent_download.py native-source/ApplePackage
(
  cd native-source/ApplePackage
  swift build -j 2 --build-tests
  swift test --skip-build --filter 'SAPAuthenticationRequestTests|LabEntDownloadTests|LabAuthRouteTests|LabStoreAMD'
  swift build -j 2 --product ApplePackageTool
)
mkdir -p native-source/age/cmd/lab-delivery-crypt
cp tools/delivery_crypto.go native-source/age/cmd/lab-delivery-crypt/main.go
cp tests/delivery_crypto_test.go native-source/age/cmd/lab-delivery-crypt/main_test.go
(
  cd native-source/age
  go test -p 2 -timeout 120s ./cmd/lab-delivery-crypt
  go build -p 2 -trimpath -o ../../delivery-crypt ./cmd/lab-delivery-crypt
)
python3 deploy/managed/circleci/runtime.py pack-and-verify
mv native-source/ApplePackage/.build native-source/ApplePackage/.build-hidden
relocated-circle-base-runtime/ApplePackageTool --help
relocated-circle-base-runtime/offline-engine --help
otool -L relocated-circle-base-runtime/ApplePackageTool
# Runtime archives are public and contain no credentials, models or third-party IPAs.

# Reuse only the just-tested public Swift build, before any credentials exist.
mv native-source/ApplePackage/.build-hidden native-source/ApplePackage/.build
python3 .github/ops/patch_cn_login.py native-source/ApplePackage
(
  cd native-source/ApplePackage
  swift build -j 2 --build-tests
  swift test --skip-build --filter 'SAPAuthenticationRequestTests|LabEntDownloadTests|LabAuthRouteTests|LabStoreAMD|LabCNLoginFlowTests|LabCNSummaryTests'
  swift build -j 2 --product ApplePackageTool
)
python3 deploy/managed/circleci/runtime.py pack-and-verify --variant cn
mv native-source/ApplePackage/.build native-source/ApplePackage/.build-hidden
relocated-circle-cn-runtime/ApplePackageTool --help
relocated-circle-cn-runtime/ApplePackageTool login-cn --help
relocated-circle-cn-runtime/ApplePackageTool resume-cn --help
relocated-circle-cn-runtime/ApplePackageTool summary-cn --help

bash deploy/managed/circleci/build-public-tf-runtime.sh
