#!/bin/sh
# Install a prebuilt, CI-verified bundle. Never compile or run tests here.
set -eu
umask 077
bundle=$1
config=$2
release=$3
expected=$4
case "$release" in *[!0-9a-f]*|'') exit 2;; esac
[ "${#release}" -eq 40 ]
[ "$(id -u)" -eq 0 ]
printf '%s  %s\n' "$expected" "$bundle" | sha256sum --check --status
# Only system runtime libraries; no compiler, pip, git or build dependencies.
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends python3 ca-certificates libssl3t64 zlib1g libstdc++6
apt-get clean
if ! id ipazake >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/ipazake --shell /usr/sbin/nologin ipazake
fi
install -d -m 0755 /opt/ipazake /opt/ipazake/releases
install -d -m 0700 /etc/ipazake
install -d -m 0700 -o ipazake -g ipazake /var/lib/ipazake
destination=/opt/ipazake/releases/$release
if [ ! -d "$destination" ]; then
  mkdir -m 0755 "$destination"
  tar -xzf "$bundle" -C "$destination" --no-same-owner
  chown -R root:root "$destination"
  chmod -R go-w "$destination"
fi
if [ -f /etc/ipazake/bot.json ]; then
  cp -p /etc/ipazake/bot.json /etc/ipazake/bot.previous.json
fi
install -m 0600 "$config" /etc/ipazake/bot.json
previous=$(readlink -f /opt/ipazake/current 2>/dev/null || true)
systemctl stop ipazake.service 2>/dev/null || true
if [ -n "$previous" ] && [ -d "$previous" ]; then
  ln -sfn "$previous" /opt/ipazake/previous
fi
ln -sfn "$destination" /opt/ipazake/current.next
mv -Tf /opt/ipazake/current.next /opt/ipazake/current
install -m 0644 "$destination/deploy/ipazake.service" /etc/systemd/system/ipazake.service
systemctl daemon-reload
systemctl enable ipazake.service
rm -f /var/lib/ipazake/health.json
systemctl restart ipazake.service
rm -f "$config" "$bundle"
echo prebuilt_service_installed
