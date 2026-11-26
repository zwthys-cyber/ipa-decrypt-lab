"""Read only the isolated Cloudflare pilot's configuration, never secret values."""
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

WORKER = "ipazake-free-control-pilot"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def api(account, token, path, data=None):
    if not re.fullmatch(r"[a-f0-9]{32}", account) or not path.startswith(("/workers/", "/d1/")) or ".." in path:
        raise ValueError("invalid_cloud_path")
    headers = {"Authorization":"Bearer " + token, "Accept":"application/json"}
    raw = None if data is None else json.dumps(data).encode()
    if raw is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request("https://api.cloudflare.com/client/v4/accounts/" + account + path,
                                     data=raw, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
            content = response.read(1048577)
            if len(content) > 1048576:
                raise ValueError("cloud_response_limit")
            value = json.loads(content)
            if value.get("success") is not True:
                raise ValueError("cloud_request_rejected")
            return value["result"]
    except urllib.error.HTTPError as error:
        raise ValueError("cloud_http_" + str(error.code)) from None

def inventory():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("github_ci_required")
    account, token = os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_API_TOKEN", "")
    if not token:
        raise ValueError("cloud_token_missing")
    settings = api(account, token, "/workers/scripts/" + WORKER + "/settings")
    bindings = {x.get("name"):x for x in settings.get("bindings", [])}
    db = bindings.get("DB", {})
    if db.get("type") != "d1" or not re.fullmatch(r"[a-f0-9-]{36}", db.get("id", "")):
        raise ValueError("pilot_d1_binding_missing")
    subdomain = api(account, token, "/workers/subdomain").get("subdomain", "")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", subdomain):
        raise ValueError("cloud_subdomain_invalid")
    exposed = api(account, token, "/workers/scripts/" + WORKER + "/subdomain")
    result = api(account, token, "/d1/database/" + db["id"] + "/query",
        dict(sql="SELECT name FROM sqlite_master WHERE type='table' AND name IN ('pilot_jobs','pilot_links','circleci_dispatches','circleci_control_jobs','circleci_claims')", params=[]))
    if not isinstance(result, list) or len(result) != 1 or result[0].get("success") is not True:
        raise ValueError("pilot_schema_read_failed")
    tables = sorted(row["name"] for row in result[0].get("results", []))
    flag = lambda name: bindings.get(name, {}).get("text") == "1"
    private = lambda name: bindings.get(name, {}).get("type") == "secret_text"
    receipt = dict(schema="circleci-cloud-inventory-v1", read_only=True, worker=WORKER,
        control_origin="https://" + WORKER + "." + subdomain + ".workers.dev",
        workers_dev_enabled=exposed.get("enabled") is True,
        pilot_enabled=flag("PILOT_ENABLED"), link_enabled=flag("PILOT_LINK_ENABLED"),
        runtime_enabled=bindings.get("PILOT_RUNTIME_MODE", {}).get("text") in ("probe", "production"),
        d1_tables=tables,
        google_refresh_configured=all(private(name) for name in
            ("PILOT_DRIVE_CLIENT_ID","PILOT_DRIVE_CLIENT_SECRET","PILOT_DRIVE_REFRESH_TOKEN")),
        google_recipient_configured=private("PILOT_DRIVE_RECIPIENT_EMAIL"),
        owner_configured="PILOT_OWNER_ID" in bindings)
    Path("circleci-cloud-inventory.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
    print(json.dumps(receipt, sort_keys=True))

def main():
    try:
        inventory()
        return 0
    except Exception as error:
        reason = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z0-9_]+", str(error)) else "cloud_inventory_failed"
        print(reason, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
