#!/usr/bin/env bash
# Sourced only by the public producer on an ephemeral CircleCI macOS runner.
set -euo pipefail
export HOMEBREW_NO_AUTO_UPDATE=1
export HOMEBREW_NO_INSTALL_CLEANUP=1
export HOMEBREW_NO_INSTALLED_DEPENDENTS_CHECK=1
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
  git -C "$destination" fetch --quiet --depth=1 --no-tags "https://github.com/$repo.git" "$revision"
  git -C "$destination" checkout --quiet --detach FETCH_HEAD
  test "$(git -C "$destination" rev-parse HEAD)" = "$revision"
}
