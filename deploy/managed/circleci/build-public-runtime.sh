#!/usr/bin/env bash
# Public source only. Never mount account credentials in this producer.
set -euo pipefail
test "${CIRCLECI:-}" = true
test -z "${GITHUB_ACTIONS:-}"
test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
test "$(sw_vers -productVersion | cut -d. -f1)" = 26
test "$(git rev-parse HEAD)" = "$CIRCLE_SHA1"
for secret_name in APPLE_ID APPLE_PASSWORD APPLE_CN_ID APPLE_CN_PASSWORD APPLE_CN_SESSION_B64 FAIRPLAY_MODEL_B64 FAIRPLAY_STATE_B64 FAIRPLAY_CN_MODEL_B64 FAIRPLAY_CN_STATE_B64 DELIVERY_AGE_IDENTITY TELEGRAM_BOT_TOKEN; do
  if [[ -n "${!secret_name:-}" ]]; then
    echo "Refusing credentials in public runtime producer" >&2
    exit 1
  fi
done
checkout_public() {
  local repo="$1" revision="$2" destination="native-source/$3"
  test ! -e "$destination"
  git init --quiet "$destination"
  git -C "$destination" fetch --depth=1 --no-tags "https://github.com/$repo.git" "$revision"
  git -C "$destination" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$destination" rev-parse HEAD)" = "$revision"
}
checkout_public Lakr233/ApplePackage 391bfe6ee6598d73e4f94b88b38b50bd6f6ec67b ApplePackage
checkout_public DrWhax/unfairplay 26a099fcb2292eaacd9e0ce89793cdbc88e516d1 unfairplay
checkout_public majd/ipatool d9c0247daea564d3ec7d04a9b015d0a29af66b04 ipatool
checkout_public FiloSottile/age b74dce4cdbe35b5e5f66c06d9612b72f89028758 age
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
relocated-circle-runtime/ApplePackageTool --help
relocated-circle-runtime/offline-engine --help
otool -L relocated-circle-runtime/ApplePackageTool
# Runtime archives are public and contain no credentials, models or third-party IPAs.
