"""Fetch only a pinned successful public CircleCI runtime on the matching ARM host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from probe import SLUG, PROJECT, BRANCH, UUID, require, validate_run
import runtime

DEFINITION = "ed763fe9-befd-4122-83df-30f5d94bb94b"
CONTRACT_PATHS = ("tools", "tests", ".github/ops", ".github/actions/export-progress",
    ".github/workflows/native-runtime-build.yml", ".github/workflows/cn-auth-runtime.yml",
    ".github/workflows/testflight-runtime-build.yml", "deploy/managed/circleci/runtime.py",
    "deploy/managed/circleci/test_runtime.py", "deploy/managed/circleci/build-public-runtime.sh",
    "deploy/managed/circleci/build-public-tf-runtime.sh", "deploy/managed/circleci/public-build-common.sh")
EXPECTED = ("commit", "workflow_id", "job_number", "source_fingerprint", "xcode", "swift", "macos", "variant", "dependencies")

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

def safe_artifact_url(url):
    p = urllib.parse.urlparse(url)
    host = p.hostname or ""
    return (p.scheme == "https" and not p.username and not p.password and p.port in (None, 443)
            and not p.fragment and (host == "output.circle-artifacts.com" or
            host.endswith(".s3.amazonaws.com") or
            re.fullmatch(r"[a-z0-9.-]+\.s3[.-][a-z0-9-]+\.amazonaws\.com", host) is not None))

class ArtifactRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 3
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(safe_artifact_url(newurl), "artifact_redirect_host")
        # Artifact requests never contain an API token or account credential.
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def api(path):
    require(path.startswith(("/project/", "/workflow/", "/runs/")) and ".." not in path
            and "?" not in path, "api_path")
    version = "3" if path.startswith("/runs/") else "2"
    req = urllib.request.Request("https://circleci.com/api/v" + version + path,
                                 headers={"Accept":"application/json"})
    with urllib.request.build_opener(NoRedirect()).open(req, timeout=30) as response:
        require(response.status == 200, "api_status")
        raw = response.read(1048577)
        require(len(raw) <= 1048576, "api_limit")
        return json.loads(raw)

def native_contract(root, ref):
    raw = subprocess.check_output(["git", "ls-tree", "-rz", ref, "--", *CONTRACT_PATHS], cwd=root)
    require(bool(raw), "source_contract_missing")
    return hashlib.sha256(raw).hexdigest()

def source_gate(root, source):
    require(re.fullmatch(r"[a-f0-9]{40}", source), "producer_source")
    exists = subprocess.run(["git", "cat-file", "-e", source + "^{commit}"], cwd=root,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    if not exists:
        subprocess.run(["git", "fetch", "--quiet", "--depth=1", "--no-tags",
                        "https://github.com/zwthys-cyber/ipa-decrypt-lab.git", source],
                       cwd=root, check=True, timeout=60)
    require(native_contract(root, "HEAD") == native_contract(root, source), "native_source_contract_changed")

def check_host(expected):
    require(os.environ.get("CIRCLECI") == "true" and not os.environ.get("GITHUB_ACTIONS"),
            "circleci_required")
    require(platform.system() == "Darwin" and platform.machine() == "arm64", "arm_macos_required")
    actual = dict(
        macos=subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip(),
        xcode=subprocess.check_output(["xcodebuild", "-version"], text=True).strip(),
        swift=subprocess.check_output(["swift", "--version"], text=True).strip())
    if expected["variant"] == "testflight":
        actual["dependencies"] = subprocess.check_output(["brew", "list", "--versions",
            "mbedtls@3", "curl", "nlohmann-json", "libzip", "cmake", "ninja"], text=True).strip()
    require(all(expected.get(k) == v for k, v in actual.items()), "runtime_host_abi_changed")

def trusted_job(pins, call=api):
    require(pins.get("schema") == "circleci-native-pins-v1" and
            re.fullmatch(r"[a-f0-9]{40}", pins.get("source", "")) and
            re.fullmatch(UUID, pins.get("workflow_id", "")) and
            type(pins.get("job_number")) is int and pins["job_number"] > 0, "invalid_runtime_pins")
    prefix = "/project/" + SLUG
    job = call(prefix + "/job/" + str(pins["job_number"]))
    require(job.get("status") == "success" and job.get("name") == "arm64-ios-archive" and
            job.get("project", {}).get("id") == PROJECT and job["project"].get("slug") == SLUG and
            job.get("executor", {}).get("resource_class") == "m4pro-medium" and
            job.get("executor", {}).get("type") == "macos", "producer_job_invalid")
    run = job.get("pipeline", {}).get("id", "")
    require(re.fullmatch(UUID, run), "producer_run_invalid")
    state = validate_run(call("/runs/" + run), pins["source"], DEFINITION)
    require(state.get("phase") == "ended" and state.get("current_outcome") == "succeeded", "producer_not_finished")
    workflow = call("/workflow/" + pins["workflow_id"])
    require(workflow.get("status") == "success" and workflow.get("pipeline_id") == run and
            workflow.get("name") == "arm64-archive-validation", "producer_workflow_invalid")
    jobs = call("/workflow/" + pins["workflow_id"] + "/job").get("items", [])
    require(len(jobs) == 1 and jobs[0].get("job_number") == pins["job_number"] and
            jobs[0].get("status") == "success" and jobs[0].get("name") == "arm64-ios-archive", "producer_job_binding")
    return prefix + "/" + str(pins["job_number"]) + "/artifacts"

def artifact(pins, variant, value):
    require(variant in runtime.VARIANTS, "invalid_variant")
    record = pins.get("variants", {}).get(variant)
    require(isinstance(record, dict) and re.fullmatch(r"[a-f0-9]{64}", record.get("archive_sha256", "")),
            "missing_archive_pin")
    expected = {k:record.get(k) for k in EXPECTED}
    require(expected["commit"] == pins["source"] and expected["workflow_id"] == pins["workflow_id"] and
            expected["job_number"] == str(pins["job_number"]) and expected["variant"] == variant, "pin_identity")
    path = "public-arm64-native-runtime/" + variant + "/native-runtime.tar.gz"
    matches = [x for x in value.get("items", []) if x.get("path") == path]
    require(len(matches) == 1 and safe_artifact_url(matches[0].get("url", "")), "artifact_missing_or_host")
    return matches[0]["url"], record["archive_sha256"], expected

def download(url, path, expected_digest):
    require(safe_artifact_url(url), "artifact_host")
    deadline, total = time.monotonic() + 180, 0
    hashed = hashlib.sha256()
    with urllib.request.build_opener(ArtifactRedirect()).open(url, timeout=30) as response:
        require(response.status == 200, "artifact_status")
        with Path(path).open("xb") as output:
            while True:
                require(time.monotonic() < deadline, "artifact_timeout")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                require(total <= runtime.MAX_ARCHIVE, "archive_limit")
                hashed.update(chunk)
                output.write(chunk)
    require(total > 0 and hashed.hexdigest() == expected_digest, "archive_digest_mismatch")

def fetch(root, pins, variant, output):
    require(not Path(output).exists(), "runtime_destination_exists")
    source_gate(root, pins.get("source", ""))
    endpoint = trusted_job(pins)
    url, digest, expected = artifact(pins, variant, api(endpoint))
    check_host(expected)
    with tempfile.TemporaryDirectory() as folder:
        archive = Path(folder) / "runtime.tar.gz"
        download(url, archive, digest)
        runtime.unpack(archive, output, expected)
    return dict(schema="circleci-native-fetch-v1", source=pins["source"],
                producer_job=pins["job_number"], variant=variant, archive_sha256=digest)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", required=True, choices=sorted(runtime.VARIANTS))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        require(os.environ.get("CIRCLECI") == "true" and not os.environ.get("GITHUB_ACTIONS"), "circleci_required")
        require(os.environ.get("CIRCLE_BRANCH") == BRANCH, "circleci_branch")
        root = Path(__file__).resolve().parents[3]
        pins = json.loads((Path(__file__).with_name("runtime-pins.json")).read_text())
        print(json.dumps(fetch(root, pins, args.variant, args.output)), flush=True)
    except Exception as error:
        message = str(error) if type(error) is ValueError and re.fullmatch(r"[a-z0-9_]+", str(error)) else "runtime_fetch_failed"
        print(message, file=__import__("sys").stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
