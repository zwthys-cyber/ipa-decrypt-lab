#!/usr/bin/env bash
set -euo pipefail

destination="${1:?package directory required}"
delivery_helper="${2:?delivery helper required}"
bot_api="${3:?Bot API executable required}"

mkdir -p "$destination/bin" "$destination/tools"
install -m 0755 "$delivery_helper" "$destination/bin/delivery-crypt"
install -m 0755 "$bot_api" "$destination/bin/telegram-bot-api"
for module in testflight_state tf_state_http account_profile version_catalog app_presentation \
  version_request app_preflight capacity telegram_daemon multi_user persistent_journal \
  telegram_controller telegram_runtime telegram_api telegram_menu telegram_queue \
  task_progress delivery_scheduler ipa_audit managed_migration managed_volume_preflight; do
  cp "tools/$module.py" "$destination/tools/"
done
printf '%s\n' "${GITHUB_SHA:?source commit required}" > "$destination/SOURCE_COMMIT"
