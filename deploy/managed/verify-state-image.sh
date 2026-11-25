#!/usr/bin/env bash
set -euo pipefail

image=${1:?Usage: verify-state-image.sh STATE_IMAGE}
volume=$(docker volume create "ipazake-state-check-$$-$RANDOM")
container=
cleanup() {
  if [[ -n "$container" ]]; then
    docker stop --time 2 "$container" >/dev/null 2>&1 || true
  fi
  docker volume rm "$volume" >/dev/null
}
trap cleanup EXIT

mount="type=volume,source=$volume,target=/var/lib/ipazake"
docker run --rm -i --network none --mount "$mount" --user 0:0 \
  --entrypoint /usr/bin/python3 "$image" - <<'PY'
import os
from pathlib import Path
import sqlite3

volume = Path("/var/lib/ipazake")
root = volume / "testflight"
root.mkdir(mode=0o700)
session = root / "session.age"
session.write_bytes(b"age-encryption.org/v1\nsynthetic CI fixture\n")
ledger = root / "acceptance.sqlite"
with sqlite3.connect(ledger) as db:
    db.execute(
        "CREATE TABLE invitations (invite TEXT PRIMARY KEY, request_id TEXT, "
        "run_id TEXT, source_commit TEXT, nonce TEXT, expires INTEGER, state TEXT)"
    )
db.close()

for path in (session, ledger):
    path.chmod(0o600)
    os.chown(path, 10001, 10001)
volume.chmod(0o700)
for path in (root, volume):
    os.chown(path, 10001, 10001)
PY

TF_STATE_API_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
export TF_STATE_API_TOKEN

verify_state() {
  container=$(docker run --rm --detach --network none --mount "$mount" \
    -e TF_STATE_API_TOKEN "$image")
  docker exec -i "$container" /usr/bin/python3 - <<'PY'
import hashlib
from http.client import HTTPConnection
import json
import os
import time

def request(method, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", 8080, timeout=1)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, json.load(response)
    finally:
        connection.close()

for attempt in range(30):
    try:
        health = request("GET", "/healthz")
        break
    except OSError:
        if attempt == 29:
            raise
        time.sleep(0.2)
assert health == (200, {"status": "ready"}), health

headers = {"Content-Type": "application/json"}
denied = request("POST", "/v1/status", body=b"{}", headers=headers)
assert denied == (401, {"status": "failed"}), denied

headers["Authorization"] = "Bearer " + os.environ["TF_STATE_API_TOKEN"]
code, result = request("POST", "/v1/status", body=b"{}", headers=headers)
fixture = b"age-encryption.org/v1\nsynthetic CI fixture\n"
assert code == 200 and result["ready"] is True, (code, result)
assert result["sha256"] == hashlib.sha256(fixture).hexdigest(), result
assert result["bytes"] == len(fixture), result
print("Mounted state is ready and status requires authorization")
PY
  docker stop --time 2 "$container" >/dev/null
  container=
}

verify_state
verify_state
