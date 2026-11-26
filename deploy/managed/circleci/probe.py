"""Bounded synthetic dispatch probe; no Apple, Telegram, Drive or production calls."""
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

REPO = "zwthys-cyber/ipa-decrypt-lab"
BRANCH = "upgrade/managed-runtime-v0.2"
SLUG = "circleci/Nt3fThGbrJQiJ92BdY1epw/bJTC8t2uZoAWRmbhUAY7y"
PROJECT = "04ca0b08-bd33-434c-a59c-5f4ca8d18688"
UUID = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def uuid(value):
    return isinstance(value, str) and re.fullmatch(UUID, value) is not None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def api(token, path, data=None):
    require((path == "/me" or path.startswith(("/project/", "/projects/", "/pipeline/", "/workflow/")))
            and ".." not in path and "?" not in path, "invalid_api_path")
    headers = {"Authorization": "Bearer " + token, "Accept": "application/json"}
    raw = None if data is None else json.dumps(data).encode()
    if raw is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request("https://circleci.com/api/v2" + path, data=raw, headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
            content = response.read(1048577)
            require(len(content) <= 1048576, "api_size_limit")
            return response.status, json.loads(content)
    except urllib.error.HTTPError as error:
        # Never print response bodies, request headers or a token-bearing URL.
        raise ValueError("circleci_http_" + str(error.code)) from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError("circleci_transport_unknown") from None

def select_definition(value):
    items = value.get("items")
    require(isinstance(items, list), "invalid_definitions")
    matches = []
    for item in items:
        if not isinstance(item, dict):
            continue
        config, checkout = item.get("config_source", {}), item.get("checkout_source", {})
        if (config.get("provider") == "github_app" and config.get("file_path") == ".circleci/config.yml"
                and config.get("repo", {}).get("full_name") == REPO
                and checkout.get("provider") == "github_app"
                and checkout.get("repo", {}).get("full_name") == REPO and uuid(item.get("id"))):
            matches.append(item["id"])
    require(len(matches) == 1, "ambiguous_or_missing_definition")
    return matches[0]

def payload(definition, commit, request_id):
    require(uuid(definition) and re.fullmatch(r"[a-f0-9]{40}", commit)
            and re.fullmatch(r"[a-f0-9]{32}", request_id), "invalid_dispatch_identity")
    return dict(definition_id=definition, config=dict(branch=BRANCH), checkout=dict(branch=BRANCH),
                parameters=dict(dispatch_probe=True, probe_source=commit, probe_id=request_id,
                                build_native_runtime=False))

def worker_receipt(commit, request_id, pipeline_id, env=None):
    env = os.environ if env is None else env
    require(env.get("CIRCLECI") == "true" and not env.get("GITHUB_ACTIONS"), "circleci_required")
    require(re.fullmatch(r"[a-f0-9]{40}", commit) and commit == env.get("CIRCLE_SHA1"),
            "source_mismatch")
    require(re.fullmatch(r"[a-f0-9]{32}", request_id) and uuid(pipeline_id), "invalid_probe_identity")
    require(env.get("CIRCLE_BRANCH") == BRANCH, "branch_mismatch")
    workflow, job = env.get("CIRCLE_WORKFLOW_ID", ""), env.get("CIRCLE_BUILD_NUM", "")
    require(uuid(workflow) and re.fullmatch(r"[1-9][0-9]*", job), "invalid_job_identity")
    return dict(schema="circleci-dispatch-probe-v1", production=False, project_slug=SLUG,
                commit=commit, request_id=request_id, pipeline_id=pipeline_id,
                workflow_id=workflow, job_number=job)

def github_probe():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_REPOSITORY") == REPO
            and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH, "github_branch_required")
    token = os.environ.get("CIRCLECI_API_TOKEN", "")
    require(bool(token) and "\n" not in token and "\r" not in token, "circleci_token_missing")
    _, identity = api(token, "/me")
    require(uuid(identity.get("id")), "token_identity_invalid")
    print("circleci_token_authenticated", flush=True)
    _, project = api(token, "/project/" + SLUG)
    require(project.get("id") == PROJECT and project.get("slug") == SLUG, "project_mismatch")
    print("circleci_project_verified", flush=True)
    _, definitions = api(token, "/projects/" + PROJECT + "/pipeline-definitions")
    print("circleci_definitions_read", flush=True)
    definition = select_definition(definitions)
    commit, request_id = os.environ["GITHUB_SHA"], secrets.token_hex(16)
    request = payload(definition, commit, request_id)
    # Synthetic only. No automatic retry after this POST, including ambiguous responses.
    code, created = api(token, "/project/" + SLUG + "/pipeline/run", request)
    require(code == 201 and uuid(created.get("id")), "dispatch_not_confirmed_no_retry")
    pipeline = created["id"]
    receipt = dict(schema="circleci-dispatch-probe-trigger-v1", production=False, project_id=PROJECT,
                   project_slug=SLUG, definition_id=definition, commit=commit, request_id=request_id,
                   pipeline_id=pipeline, status="submitted")
    print(json.dumps(receipt), flush=True)
    deadline = time.monotonic() + 480
    workflow_id = None
    while time.monotonic() < deadline:
        _, state = api(token, "/pipeline/" + pipeline)
        require(state.get("project_slug") == SLUG and not state.get("errors"), "pipeline_failed")
        _, workflows = api(token, "/pipeline/" + pipeline + "/workflow")
        items = workflows.get("items")
        require(isinstance(items, list) and len(items) <= 1, "unexpected_workflows")
        if items:
            item = items[0]
            require(item.get("name") == "synthetic-dispatch-probe" and item.get("pipeline_id") == pipeline
                    and uuid(item.get("id")), "workflow_mismatch")
            workflow_id = item["id"]
            if item.get("status") == "success":
                _, jobs = api(token, "/workflow/" + workflow_id + "/job")
                rows = jobs.get("items", [])
                require(len(rows) == 1 and rows[0].get("name") == "dispatch-contract-probe"
                        and rows[0].get("status") == "success"
                        and type(rows[0].get("job_number")) is int, "job_mismatch")
                receipt.update(status="success", workflow_id=workflow_id, job_number=rows[0]["job_number"])
                Path("circleci-probe-receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
                print(json.dumps(receipt), flush=True)
                return
            require(item.get("status") not in ("failed", "error", "canceled", "unauthorized", "not_run"),
                    "probe_workflow_failed")
        time.sleep(10)
    raise ValueError("probe_pending_no_retry")

def main():
    try:
        if sys.argv[1:] == ["github"]:
            github_probe()
        elif sys.argv[1:] == ["worker"]:
            receipt = worker_receipt(os.environ.get("PROBE_SOURCE", ""), os.environ.get("PROBE_ID", ""),
                                     os.environ.get("PROBE_PIPELINE", ""))
            Path("dispatch-probe-out").mkdir()
            Path("dispatch-probe-out/receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
            print(json.dumps(receipt))
        else:
            raise ValueError("invalid_command")
    except Exception as error:
        # Messages generated by this file are fixed tokens; do not expose third-party exceptions.
        message = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z0-9_]+", str(error)) else "probe_failed"
        print(message, file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
