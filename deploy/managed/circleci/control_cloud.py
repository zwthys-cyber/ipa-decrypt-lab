"""Deploy only the CI-tested isolated probe and verify a signed, no-op cloud roundtrip."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import urllib.error
import urllib.request
from cloud_inventory import api, NoRedirect, WORKER

OWNER = re.compile(r"[1-9][0-9]{0,15}")
SHA = re.compile(r"[a-f0-9]{40}")

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def prepared_metadata(settings, source, origin):
    bindings = settings.get("bindings")
    require(isinstance(bindings, list) and SHA.fullmatch(source), "cloud_settings_invalid")
    names = {x.get("name"):x for x in bindings}
    require(names.get("DB", {}).get("type") == "d1", "existing_d1_required")
    require(names.get("PILOT_ENABLED", {}).get("text") != "1" and
            names.get("PILOT_LINK_ENABLED", {}).get("text") != "1", "pilot_must_be_disabled")
    values = dict(PILOT_RUNTIME_MODE="probe", CIRCLECI_SOURCE_SHA=source, PILOT_CONTROL_ORIGIN=origin)
    preserved = [dict(x) for x in bindings if x.get("type") != "secret_text" and x.get("name") not in values]
    preserved += [dict(type="plain_text", name=k, text=v) for k,v in values.items()]
    return dict(main_module="worker.mjs", compatibility_date=settings.get("compatibility_date") or "2026-07-30",
        compatibility_flags=settings.get("compatibility_flags") or [], bindings=preserved,
        keep_bindings=["secret_text"], logpush=False, observability=dict(enabled=False))

def multipart(metadata, source):
    boundary = "circleci-control-" + secrets.token_hex(16)
    chunks = []
    for name, filename, content_type, raw in (
        ("metadata", None, "application/json", json.dumps(metadata).encode()),
        ("worker.mjs", "worker.mjs", "application/javascript+module", source)):
        header = 'Content-Disposition: form-data; name="' + name + '"'
        if filename:
            header += '; filename="' + filename + '"'
        chunks.append(("--" + boundary + "\r\n" + header + "\r\nContent-Type: " +
                       content_type + "\r\n\r\n").encode() + raw + b"\r\n")
    return b"".join(chunks) + ("--" + boundary + "--\r\n").encode(), "multipart/form-data; boundary=" + boundary

def public_call(origin, token, path, value):
    require(re.fullmatch(r"https://ipazake-free-control-pilot\.[a-z0-9][a-z0-9-]{0,62}\.workers\.dev", origin)
            and path in ("/v1/runtime/probe-init", "/v1/runtime/probe-submit", "/v1/runtime/probe-status"),
            "control_origin_invalid")
    req = urllib.request.Request(origin + path, data=json.dumps(value).encode(),
        headers={"Authorization":"Bearer " + token, "Content-Type":"application/json",
                 "User-Agent":"ipa-decrypt-control-probe/0.2"}, method="POST")
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=25) as response:
        raw = response.read(16385)
        require(len(raw) <= 16384, "control_response_limit")
        return json.loads(raw)

def deploy(bundle):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and
        os.environ.get("GITHUB_REPOSITORY") == "zwthys-cyber/ipa-decrypt-lab" and
        os.environ.get("GITHUB_REF") == "refs/heads/upgrade/managed-runtime-v0.2", "github_branch_required")
    source = os.environ.get("GITHUB_SHA", "")
    account, token = os.environ.get("CF_ACCOUNT_ID", ""), os.environ.get("CF_API_TOKEN", "")
    circle, owner = os.environ.get("CIRCLECI_API_TOKEN", ""), os.environ.get("RUNTIME_OWNER_ID", "")
    require(circle and OWNER.fullmatch(owner), "cloud_credentials_missing")
    bundle = Path(bundle)
    require((bundle.parent / "BUILDINFO").read_text() == "source_commit=" + source + "\n", "candidate_source_mismatch")
    raw = bundle.read_bytes()
    require(0 < len(raw) <= 524288, "candidate_size")
    path = "/workers/scripts/" + WORKER
    before = api(account, token, path + "/settings")
    subdomain = api(account, token, "/workers/subdomain").get("subdomain", "")
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", subdomain), "cloud_subdomain_invalid")
    require(api(account, token, path + "/subdomain").get("enabled") is True, "existing_worker_url_required")
    origin = "https://" + WORKER + "." + subdomain + ".workers.dev"
    metadata = prepared_metadata(before, source, origin)
    receipt = dict(schema="circleci-cloud-control-proof-v1", source_commit=source,
        worker=WORKER, bundle_sha256=hashlib.sha256(raw).hexdigest(), production=False,
        private_operation=False, status="preflight_verified")
    def save():
        Path("circleci-cloud-control-proof.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
        print(json.dumps(receipt, sort_keys=True), flush=True)
    save()
    content, content_type = multipart(metadata, raw)
    api(account, token, path, content, method="PUT", content_type=content_type)
    receipt["status"] = "candidate_uploaded"
    save()
    control = secrets.token_urlsafe(48)
    # This is the server-side dispatch token; it never reaches CircleCI task parameters.
    for name, value in (("CIRCLECI_API_TOKEN", circle), ("RUNTIME_OWNER_ID", owner),
                        ("CIRCLECI_CONTROL_TOKEN", control)):
        api(account, token, path + "/secrets", dict(name=name, type="secret_text", text=value), method="PUT")
    after = api(account, token, path + "/settings")
    old = {x["name"]:x for x in before["bindings"]}
    current = {x["name"]:x for x in after["bindings"]}
    previous = {x["name"] for x in before["bindings"] if x.get("type") == "secret_text"}
    require(previous <= {x["name"] for x in after["bindings"] if x.get("type") == "secret_text"},
            "existing_secret_bindings_changed")
    require(current.get("DB", {}).get("id") == old["DB"].get("id"), "existing_d1_changed")
    for name in ("PILOT_ENABLED", "PILOT_LINK_ENABLED"):
        require(current.get(name) == old.get(name), "pilot_flag_changed")
    require(current.get("CIRCLECI_SOURCE_SHA", {}).get("text") == source, "control_source_mismatch")
    receipt.update(status="bindings_verified", existing_secrets_preserved=True, existing_d1_preserved=True,
                   telegram_disabled=True)
    save()
    # Additive initialization is executed through the already-authorized Worker D1 binding.
    initialized = None
    for attempt in range(6):
        try:
            initialized = public_call(origin, control, "/v1/runtime/probe-init", {})
            break
        except urllib.error.HTTPError as error:
            if error.code not in (404, 503):
                raise ValueError("control_init_http_" + str(error.code)) from None
            time.sleep(3)
    require(initialized and initialized.get("ok") is True, "control_init_failed")
    diagnostic = public_call(origin, control, "/v1/runtime/probe-diagnostics", {})
    print(json.dumps(dict(stage="circleci_provider_identity", **diagnostic)), flush=True)
    require(diagnostic.get("owner_authenticated") is True, "cloud_circleci_identity_unavailable")
    # Explicit retirement is limited server-side to the one audited, credential-free historical probe.
    retired = public_call(origin, control, "/v1/runtime/probe-retire",
        dict(job_id="pilot_e942f4db020cb1e680e66f842302fcdf",
             source_sha="e6802e32bf7ae98762491178eb95dd3915e067a5"))
    require(retired.get("ok") is True and retired.get("original_task_rearmed") is False, "audited_probe_resolution_failed")
    probe_id = secrets.token_hex(16)
    logical_job = "pilot_" + probe_id
    receipt.update(job_id=logical_job, status="awaiting_cloud_roundtrip")
    save()
    # One submit only. Even an uncertain response is resolved by reading this same logical job.
    try:
        submitted = public_call(origin, control, "/v1/runtime/probe-submit", dict(probe_id=probe_id))
        require(submitted.get("ok") is True and submitted.get("job_id") == logical_job,
                "control_submit_unconfirmed")
    except (urllib.error.URLError, TimeoutError):
        pass
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        value = public_call(origin, control, "/v1/runtime/probe-status", dict(job_id=logical_job))
        if value.get("state") == "finished" and value.get("claimed") is True and value.get("probe_finished") is True:
            receipt.update(status="verified", signed_claim_verified=True, durable_completion_verified=True)
            save()
            return
        if value.get("state") in ("unknown", "intent"):
            print(json.dumps(dict(stage="dispatch_diagnostic", **value)), flush=True)
            raise ValueError("cloud_dispatch_ambiguous_no_retry")
        time.sleep(10)
    raise ValueError("cloud_probe_pending_no_retry")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    try:
        deploy(args.bundle)
        return 0
    except Exception as error:
        reason = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z0-9_]+", str(error)) else "cloud_control_probe_failed"
        print(reason, file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
