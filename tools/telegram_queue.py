"""Fixed-repository GitHub queue and private encrypted artifact transport."""
import hashlib
from app_presentation import filename as app_filename, thumbnail as app_thumbnail
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from version_request import selector, resolved_marker, verify_version
from telegram_api import NoRedirect, APIError
from app_preflight import check_app, MESSAGES, STEP_NAMES
from ipa_audit import audit
from delivery_scheduler import matches, retryable, alternate, MAX_RUNS, PRIMARY_RUNNER, version_from_run

REPOSITORY = "zwthys-cyber/ipa-decrypt-lab"
WORKFLOW = "private-delivery.yml"
from capacity import (MAX_IPA_BYTES, MAX_CIPHER_BYTES, MAX_ARTIFACT_BYTES,
                      MIN_FREE_BYTES, CRYPTO_TIMEOUT, TELEGRAM_TIMEOUT)
MAX_FILE = MAX_IPA_BYTES
def failure_kind(exc):
    names={"URLError","HTTPError","TimeoutError","PermissionError","FileNotFoundError",
           "BadZipFile","JSONDecodeError","OSError","TypeError","ValueError","AttributeError",
           "RuntimeError","QueueError","APIError","OperationalError"}
    name=type(exc).__name__
    return name if name in names else "unexpected"

class QueueError(RuntimeError):
    pass

def require(ok, status):
    if not ok:
        raise QueueError(status)

def request_id(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value), "invalid_request_id")
    return value

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()

class GitHub:
    def __init__(self, token):
        require(bool(token), "missing_github_token")
        self.token = token
        self.checks_readable = True
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, payload=None, method="GET", limit=4*1024*1024):
        require((path.startswith("/actions/") or
                 re.fullmatch(r"/check-runs(?:/[1-9][0-9]*)?",path) or
                 re.fullmatch(r"/commits/[a-f0-9]{40}/check-runs\?check_name=delivery-journal-[a-f0-9]{32}&filter=all&per_page=100&page=[1-5]",path) or
                 re.fullmatch(r"/commits/[a-f0-9]{40}/check-runs\?check_name=delivery-progress-[a-f0-9]{32}&per_page=100",path))
                and "\n" not in path, "invalid_github_path")
        request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
            data=None if payload is None else json.dumps(payload).encode(),
            method=method, headers={"Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10",
            "Content-Type": "application/json", "User-Agent": "ipa-private-delivery"})
        try:
            with self.opener.open(request, timeout=40) as response:
                raw = response.read(limit + 1)
                require(len(raw) <= limit, "github_response_too_large")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            status = "github_permission_denied" if exc.code in (401,403) else "github_request_rejected"
            exc.close()
            raise QueueError(status) from None
        except (OSError, ValueError, http.client.HTTPException):
            # A POST timeout may still have created a run. Never blindly retry it.
            raise QueueError("github_transport_unknown") from None

    def read_checks(self,path):
        if not self.checks_readable:
            return None
        try:
            return self.call(path)
        except QueueError as exc:
            if str(exc)=="github_permission_denied":
                self.checks_readable=False
                return None
            raise

    def runs(self, rid):
        request_id(rid)
        found=[]
        # Bounded alpha sessions create few runs; do not expose arbitrary workflow access.
        for page in (1,2,3):
            data = self.call("/actions/workflows/" + WORKFLOW + "/runs?event=workflow_dispatch&per_page=100&page=" + str(page))
            require(isinstance(data, dict) and isinstance(data.get("workflow_runs"), list), "invalid_run_list")
            for run in data["workflow_runs"]:
                if (matches(run,rid)
                        and run.get("event") == "workflow_dispatch"
                        and run.get("head_branch") == "main"
                        and run.get("path") == ".github/workflows/" + WORKFLOW):
                    found.append(run)
            if len(data["workflow_runs"]) < 100:
                break
        return sorted(found,key=lambda r:r["id"],reverse=True)

    def find(self,rid):
        runs=self.runs(rid)
        for run in runs:
            if run.get("status")=="completed" and run.get("conclusion")=="success":
                return run
        for run in runs:
            if run.get("status")!="completed":
                return run
        return runs[0] if runs else None

    def preflight_app(self, app, historical=False):
        return check_app(app, historical=historical)

    def dispatch(self, app, rid, version=""):
        version=selector(version)
        request_id(rid)
        require(re.fullmatch(r"[1-9][0-9]{4,19}", app or ""), "invalid_app_id")
        existing = self.find(rid)
        if existing:
            return existing
        response = self.call("/actions/workflows/" + WORKFLOW + "/dispatches",
            {"ref":"main", "inputs":{"mode":"export", "app_id":app, "request_id":rid,"runner":PRIMARY_RUNNER, **({"version":version} if version else {})}}, "POST")
        if isinstance(response, dict) and type(response.get("workflow_run_id")) is int:
            return {"id":response["workflow_run_id"], "status":"queued"}
        return {"status":"dispatch_pending"}

    def jobs(self,run):
        data=self.call("/actions/runs/"+str(int(run["id"]))+"/jobs?per_page=100")
        require(isinstance(data,dict) and isinstance(data.get("jobs"),list),"invalid_job_list")
        return data["jobs"]

    def queued_confirmed(self,run,jobs):
        # Actions run/job metadata may lag. Cross-check the native Checks API
        # before cancelling work that only appears unassigned in that view.
        if not jobs or not isinstance(run.get("head_sha"),str):
            return False
        for job in jobs:
            identifier=job.get("id")
            if type(identifier) is not int or identifier<=0:
                return False
            check=self.read_checks("/check-runs/"+str(identifier))
            if (not isinstance(check,dict) or check.get("status")!="queued"
                    or check.get("head_sha")!=run["head_sha"]
                    or check.get("app",{}).get("slug")!="github-actions"):
                return False
        return True

    def retry(self,app,rid,old_id,cancel_requested=False,version=""):
        version=selector(version)
        request_id(rid)
        require(re.fullmatch(r"[1-9][0-9]{4,19}",app or ""),"missing_retry_app")
        runs=self.runs(rid)
        require(bool(runs),"retry_source_missing")
        # A visible new attempt or successful result wins over another POST.
        if runs[0]["id"]!=old_id or any(r.get("conclusion")=="success" for r in runs):
            return self.find(rid)
        require(len(runs)<MAX_RUNS,"runner_retry_budget_exhausted")
        old=self.call("/actions/runs/"+str(int(old_id)))
        require(matches(old,rid) and old.get("head_branch")=="main"
                and old.get("event")=="workflow_dispatch"
                and old.get("path")==".github/workflows/"+WORKFLOW,"invalid_retry_source")
        require(version_from_run(old)==version,"retry_version_mismatch")
        jobs=self.jobs(old)
        require(retryable(old,jobs,cancel_requested),"retry_not_safe")
        target=alternate(jobs)
        result=self.call("/actions/workflows/"+WORKFLOW+"/dispatches",
            {"ref":"main","inputs":{"mode":"export","app_id":app,"request_id":rid,"runner":target, **({"version":version} if version else {})}},"POST")
        return {"status":"dispatch_pending","runner":target,
                **({"id":result["workflow_run_id"]} if isinstance(result,dict)
                   and type(result.get("workflow_run_id")) is int else {})}

    def progress(self, run, rid):
        from task_progress import parse_stage
        request_id(rid)
        commit=run.get("head_sha","")
        require(re.fullmatch(r"[a-f0-9]{40}",commit), "invalid_progress_commit")
        data=self.read_checks("/commits/"+commit+"/check-runs?check_name=delivery-progress-"+rid+"&per_page=100") or {}
        for check in data.get("check_runs",[]):
            stage=parse_stage(check,rid,run["id"])
            if stage:
                return stage
        build_steps={"Compile native client and test targets","Build and test bounded kbsync helper","Build and test offline backend",
                     "Test independent signing request construction","Build independent native client",
                     "Build and test private delivery encryption"}
        for job in self.jobs(run):
            for step in job.get("steps",[]):
                if step.get("status")=="in_progress" and step.get("name") in build_steps:
                    return "building"
            identifier=job.get("id")
            if type(identifier) is int and identifier>0:
                check=self.read_checks("/check-runs/"+str(identifier))
                if (isinstance(check,dict) and isinstance(check.get("app"),dict)
                        and check["app"].get("slug")=="github-actions"
                        and check.get("head_sha")==run.get("head_sha")
                        and check.get("status")=="in_progress"):
                    return "preparing"
            if not self.checks_readable and job.get("status")=="in_progress":
                return "preparing"
        return None

    def failure_reason(self,run):
        messages = {
            "IPA exceeds 2000 MB capacity": "IPA 超过当前容量上限：2000 MB（2,000,000,000 字节），或解压后的程序规模超出检查预算。",
            "Historical version unavailable": "指定旧版本查询或下载未完成，可能已不可下载或超过查询预算；未回退最新版。可核对版本号，或提供 Apple 历史版本 ID 重试。",
            "Insufficient private workspace": "处理所需磁盘空间不足，任务已停止，请稍后重试。",
        }
        messages.update({name:MESSAGES[code] for code,name in STEP_NAMES.items() if name not in messages})
        for job in self.jobs(run):
            for step in job.get("steps",[]):
                if step.get("conclusion") == "failure" and step.get("name") in messages:
                    return messages[step["name"]]
        return ""

    def cancel(self, rid):
        run = self.find(rid)
        require(run is not None, "run_not_found")
        if run.get("status") != "completed":
            self.call("/actions/runs/" + str(int(run["id"])) + "/cancel", {}, "POST")

    def archive(self, artifact_id, destination):
        destination=Path(destination)
        require(not destination.exists() and not destination.is_symlink(),"artifact_destination_exists")
        # GET-only transport retry. Never retry Telegram sends or job submissions.
        for attempt in range(2):
            try:
                return self._archive_once(artifact_id,destination)
            except (OSError,http.client.HTTPException) as exc:
                print(json.dumps({"schema":"artifact-retrieval-v1","status":"transport_exception",
                                  "exception_kind":failure_kind(exc),"attempt":attempt+1}),flush=True)
                destination.unlink(missing_ok=True)
                if attempt:
                    raise QueueError("artifact_transport_failed") from None
            except QueueError as exc:
                if str(exc)!="artifact_transport_failed":
                    raise
                destination.unlink(missing_ok=True)
                if attempt:
                    raise

    def _archive_once(self, artifact_id, destination):
        require(type(artifact_id) is int and artifact_id > 0, "invalid_artifact_id")
        request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY
            + "/actions/artifacts/" + str(artifact_id) + "/zip",
            headers={"Authorization":"Bearer " + self.token, "User-Agent":"ipa-private-delivery"})
        try:
            response = self.opener.open(request, timeout=40)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301,302,303,307):
                exc.close()
                raise QueueError("artifact_download_rejected") from None
            location = exc.headers.get("Location", "")
            exc.close()
            parsed = urllib.parse.urlsplit(location)
            require(parsed.scheme == "https" and parsed.port in (None,443) and not parsed.username
                    and not parsed.password and not parsed.fragment and parsed.hostname
                    and (parsed.hostname.endswith(".blob.core.windows.net")
                         or parsed.hostname.endswith(".githubusercontent.com")),
                    "untrusted_artifact_redirect")
            # Signed download URL gets no GitHub Authorization header.
            response = self.opener.open(urllib.request.Request(location,
                headers={"User-Agent":"ipa-private-delivery"}), timeout=60)
        try:
            with response, open(destination, "xb") as output:
                total = 0
                while True:
                    block = response.read(1024*1024)
                    if not block:
                        break
                    total += len(block)
                    require(total <= MAX_ARTIFACT_BYTES, "artifact_too_large")
                    output.write(block)
                require(total > 0, "empty_artifact")
        except (OSError, http.client.HTTPException):
            raise QueueError("artifact_transport_failed") from None

    def artifact_ready(self,run,rid):
        request_id(rid)
        if (not isinstance(run,dict) or type(run.get("id")) is not int
                or not matches(run,rid) or run.get("event")!="workflow_dispatch"
                or run.get("head_branch")!="main"
                or run.get("path")!=".github/workflows/"+WORKFLOW):
            return False
        if run.get("status")=="completed":
            return run.get("conclusion")=="success"
        if run.get("status") not in ("in_progress","queued","waiting","pending"):
            return False
        if self.progress(run,rid)!="artifact_ready":
            return False
        data=self.call("/actions/runs/"+str(run["id"])+"/artifacts?per_page=100")
        require(isinstance(data,dict) and isinstance(data.get("artifacts"),list),"invalid_artifact_list")
        candidates=[a for a in data["artifacts"] if isinstance(a,dict) and a.get("name")=="delivery-"+rid
                    and a.get("expired") is False]
        return (len(candidates)==1 and type(candidates[0].get("id")) is int and candidates[0]["id"]>0
                and type(candidates[0].get("size_in_bytes")) is int
                and 0<candidates[0]["size_in_bytes"]<=MAX_ARTIFACT_BYTES
                and isinstance(candidates[0].get("digest"),str)
                and re.fullmatch(r"sha256:[a-f0-9]{64}",candidates[0]["digest"]) is not None)

    def deliver(self, rid, bot, owner, crypt, progress=None):
        request_id(rid)
        progress = progress or (lambda stage: None)
        progress("retrieving")
        run = self.find(rid)
        require(run is not None and self.artifact_ready(run,rid), "artifact_not_ready")
        requested_version = version_from_run(run)
        run_id = int(run["id"])
        artifacts = self.call("/actions/runs/" + str(run_id) + "/artifacts?per_page=100")
        require(isinstance(artifacts, dict), "invalid_artifact_list")
        found = [a for a in artifacts.get("artifacts", []) if a.get("name") == "delivery-" + rid
                 and a.get("expired") is False]
        require(len(found) == 1, "delivery_artifact_missing_or_expired")
        with tempfile.TemporaryDirectory(prefix="tg-private-delivery-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            require(shutil.disk_usage(root).free >= MIN_FREE_BYTES, "insufficient_delivery_disk")
            bundle = root/"encrypted.zip"
            self.archive(found[0]["id"], bundle)
            archive_digest=found[0].get("digest")
            if archive_digest is not None:
                require(isinstance(archive_digest,str) and
                        re.fullmatch(r"sha256:[a-f0-9]{64}",archive_digest) and
                        sha256(bundle)==archive_digest.removeprefix("sha256:"),
                        "artifact_archive_digest_mismatch")
            with zipfile.ZipFile(bundle) as z:
                entries = z.infolist()
                require(len(entries) == 2 and {e.filename for e in entries} ==
                        {"package.ipa.age","receipt.json"}, "unexpected_artifact_members")
                require(z.getinfo("receipt.json").file_size <= 16384
                        and z.getinfo("package.ipa.age").file_size <= MAX_CIPHER_BYTES,
                        "invalid_artifact_sizes")
                receipt = json.loads(z.read("receipt.json"))
                validate_receipt(receipt, rid, run_id, run["head_sha"])
                require(receipt.get("requested_version","")==requested_version,"receipt_version_mismatch")
                if requested_version:
                    resolved_marker("IPA_LAB_VERSION:" + str(receipt.get("external_version_id","")) + ":" + str(receipt.get("resolved_version","")), requested_version)
                encrypted = root/"package.ipa.age"
                with z.open("package.ipa.age") as src, encrypted.open("xb") as dst:
                    total = 0
                    while True:
                        block = src.read(1024*1024)
                        if not block: break
                        total += len(block)
                        require(total <= MAX_CIPHER_BYTES, "ciphertext_too_large")
                        dst.write(block)
            bundle.unlink()
            require(encrypted.stat().st_size == receipt["ciphertext_bytes"]
                    and sha256(encrypted) == receipt["ciphertext_sha256"], "ciphertext_digest_mismatch")
            progress("delivery_verifying")
            output = root/(receipt["app_id"] + ("_" + receipt["resolved_version"] if requested_version else "") + "_decrypted.ipa")
            env = {k:os.environ[k] for k in ("PATH","HOME","LANG","DELIVERY_AGE_IDENTITY","LAB_RUNTIME") if k in os.environ}
            if os.environ.get("GITHUB_ACTIONS")=="true":
                env["GITHUB_ACTIONS"] = "true"
            completed = subprocess.run([crypt,"decrypt",str(encrypted),str(output)], env=env,
                stdin=subprocess.DEVNULL, capture_output=True, timeout=CRYPTO_TIMEOUT)
            require(completed.returncode == 0 and output.is_file(), "delivery_decryption_rejected")
            require(output.stat().st_size == receipt["plaintext_bytes"]
                    and sha256(output) == receipt["plaintext_sha256"], "plaintext_digest_mismatch")
            encrypted.unlink()
            # Independent Linux archive/Mach-O structural check after authenticated decryption.
            info = audit(output)
            verify_version(info, requested_version, receipt.get("resolved_version",""))
            require(info["encrypted_slice_count"] == 0, "delivery_contains_encrypted_images")
            with zipfile.ZipFile(output) as z:
                require(not any(personalized(e.filename) for e in z.infolist()), "account_member_retained")
            require(bot.base == "http://127.0.0.1:8081", "large_file_server_required")
            # Local server reads private local file; no multipart buffering and no public link.
            require(output.stat().st_size <= MAX_FILE, "telegram_file_exceeds_2000mb")
            named_output = root/app_filename(info, receipt["app_id"])
            if named_output != output:
                require(not named_output.exists(), "delivery_name_collision")
                output.rename(named_output)
                output = named_output
            icon = app_thumbnail(output, receipt["app_id"])
            progress("uploading")
            reply = bot.document( {"chat_id":owner, "document":output.as_uri(),
                "caption":"IPA 已完成明文校验；已移除账号元数据。\n需要重签名后安装，尚未验证实际运行。\n任务：" + rid,
                "disable_content_type_detection":True}, icon, timeout=TELEGRAM_TIMEOUT)
            require(isinstance(reply, dict) and type(reply.get("message_id")) is int
                    and reply.get("chat",{}).get("id") == owner
                    and reply.get("document",{}).get("file_size") == output.stat().st_size,
                    "telegram_delivery_unconfirmed")
            return {"status":"telegram_file_delivered", "request_id":rid,
                    "bytes":output.stat().st_size, "plaintext_verified":True, "runtime_verified":False}

def personalized(name):
    parts = name.rstrip("/").lower().split("/")
    return ("sc_info" in parts or parts[-1] == "itunesmetadata.plist"
            or parts[-1].endswith((".sinf",".supf",".supp")))

def validate_receipt(r, rid, run_id, commit):
    require(isinstance(r, dict) and r.get("schema") == "ipa-private-delivery-v1"
        and r.get("status") == "encrypted_artifact_ready" and r.get("request_id") == rid
        and r.get("run_id") == str(run_id) and r.get("source_commit") == commit
        and r.get("plaintext_verified") is True and r.get("account_data_removed") is True
        and r.get("plaintext_published") is False and r.get("runtime_verified") is False,
        "invalid_delivery_receipt")
    require(re.fullmatch(r"[1-9][0-9]{4,19}", r.get("app_id","")), "invalid_delivery_app")
    for key in ("plaintext_bytes","ciphertext_bytes"):
        require(type(r.get(key)) is int and 0 < r[key] <= (MAX_FILE if key=="plaintext_bytes" else MAX_CIPHER_BYTES), "invalid_delivery_size")
    for key in ("plaintext_sha256","ciphertext_sha256"):
        require(re.fullmatch(r"[a-f0-9]{64}",r.get(key,"")), "invalid_delivery_digest")
