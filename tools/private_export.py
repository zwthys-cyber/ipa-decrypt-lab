"""Export only fully verified IPA as encrypted, short-lived delivery material."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import shutil
import tempfile
import zipfile
import urllib.error
from ipa_audit import audit, AuditError
from task_progress import WorkerProgress
from native_store import classify, classify_download, run
from offline_verify import readiness
from store_download import app_id, metadata
from version_request import selector, resolved_marker, verify_version, VersionError

from capacity import (MAX_IPA_BYTES, MAX_EXPANDED_BYTES, MIN_FREE_BYTES,
                      DOWNLOAD_TIMEOUT, DECRYPT_TIMEOUT, CRYPTO_TIMEOUT)
MAX_BYTES = MAX_IPA_BYTES
class ExportError(RuntimeError):
    pass

def audit_failure(exc):
    # Only literal, reviewed audit reasons may leave the private runner.
    reasons = {
        "archive entry limit exceeded": "archive_entry_limit",
        "Mach-O member size limit exceeded": "macho_member_limit",
        "audit read budget exceeded": "audit_read_limit",
        "symlink entries unsupported": "archive_symlink_unsupported",
        "duplicate archive path": "archive_duplicate_path",
        "unsafe archive path": "archive_unsafe_path",
        "invalid load command size": "macho_load_command_invalid",
        "Info.plist size limit exceeded": "info_plist_limit",
        "root executable is not a supported Mach-O": "root_macho_unsupported",
    }
    return reasons.get(str(exc), "ipa_structure_rejected")

def check_capacity(info, directory):
    declared = info.get("fileSizeBytes") if isinstance(info, dict) else None
    if isinstance(declared, str) and declared.isdecimal():
        declared = int(declared)
    if type(declared) is int:
        require(0 < declared <= MAX_BYTES, "source_too_large")
    require(shutil.disk_usage(directory).free >= MIN_FREE_BYTES, "insufficient_export_disk")

def require(condition, status):
    if not condition:
        raise ExportError(status)

def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def inventory(info, encrypted_only=False):
    found = {}
    for binary in info["binaries"]:
        for s in binary["slices"]:
            enc = s.get("encryption")
            if encrypted_only and (not enc or not enc["cryptid"]):
                continue
            key = (binary["path"], s.get("fat_offset", 0), s["cpu_type"], s["cpu_subtype"])
            require(key not in found, "duplicate_image_inventory")
            found[key] = enc
    return found

def validate_report(report, before, output):
    expected = inventory(before, encrypted_only=True)
    require(bool(expected), "no_encrypted_images")
    require(isinstance(report, dict) and report.get("schema") == "unfairplay-decryption-v2"
            and report.get("complete") is True and report.get("plaintext_verified") is True,
            "unverified_plaintext")
    images = report.get("images")
    require(isinstance(images, list) and len(images) == len(expected)
            and type(report.get("encrypted_image_count")) is int
            and report["encrypted_image_count"] == len(expected), "incomplete_image_report")
    require(isinstance(report.get("account_data"), dict)
            and report["account_data"].get("stripped") is True, "account_data_not_stripped")
    seen, pages = set(), 0
    for image in images:
        require(isinstance(image, dict), "invalid_image_report")
        key = (image.get("member"), image.get("slice_offset"), image.get("cpu_type"), image.get("cpu_subtype"))
        require(key in expected and key not in seen, "image_inventory_mismatch")
        seen.add(key)
        source = expected[key]
        count = image.get("pages")
        require(type(count) is int and 0 < count <= 1024 * 1024
                and count * 4096 == source["size"]
                and image.get("cryptoff") == source["offset"]
                and image.get("cryptsize") == source["size"]
                and image.get("cryptid_before") == 1 and image.get("cryptid_after") == 0
                and image.get("exact_mutation_scope") is True
                and image.get("plaintext_validation") == "code-directory-pre-encryption-hashes",
                "invalid_plaintext_proof")
        hashes = image.get("pre_encryption_code_directories")
        require(isinstance(hashes, list) and bool(hashes), "missing_plaintext_hashes")
        for h in hashes:
            require(isinstance(h, dict) and type(h.get("slot_count")) is int
                    and h["slot_count"] > 0 and h.get("matched_slots") == h["slot_count"],
                    "plaintext_hash_mismatch")
        pages += count
    require(type(report.get("decrypted_page_count")) is int
            and report["decrypted_page_count"] == pages, "page_count_mismatch")
    require(report.get("output", {}).get("sha256") == digest(output), "output_digest_mismatch")
    return len(expected), pages

def account_member(name):
    parts = name.rstrip("/").lower().split("/")
    return ("sc_info" in parts or parts[-1] == "itunesmetadata.plist"
            or parts[-1].endswith((".sinf", ".supf", ".supp")))

def scrub_archive(source, target):
    # Remove Store metadata entirely, beyond upstream's known purchaser-field filter.
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "x") as dst:
        for entry in src.infolist():
            if account_member(entry.filename):
                continue
            require(entry.file_size <= MAX_BYTES, "member_too_large")
            with src.open(entry) as reader, dst.open(entry, "w") as writer:
                remaining = entry.file_size
                while remaining:
                    block = reader.read(min(1024 * 1024, remaining))
                    require(bool(block), "truncated_member")
                    writer.write(block)
                    remaining -= len(block)
                require(reader.read(1) == b"", "member_size_mismatch")
    target.chmod(0o600)

def verify_output(path, before):
    require(path.is_file() and 0 < path.stat().st_size <= MAX_BYTES, "invalid_output_size")
    after = audit(path)
    require(after["bundle_id"] == before["bundle_id"]
            and after["encrypted_slice_count"] == 0
            and set(inventory(after)) == set(inventory(before)), "output_inventory_mismatch")
    with zipfile.ZipFile(path) as archive:
        require(sum(x.file_size for x in archive.infolist()) <= MAX_EXPANDED_BYTES,
                "archive_expansion_limit")
        require(not any(account_member(x.filename) for x in archive.infolist()),
                "personalized_member_retained")
        require(archive.testzip() is None, "output_crc_failed")
    return after

def export(binary, engine, crypt, target, request_id, recipient, output_dir, progress=None):
    progress = progress or (lambda stage: None)
    require(os.environ.get("GITHUB_ACTIONS") == "true", "requires_github_actions")
    require(re.fullmatch(r"[a-f0-9]{32}", request_id) is not None, "invalid_request_id")
    requested = selector(os.environ.get("DELIVERY_VERSION", ""))
    identifier = app_id(target)
    require(identifier == target, "canonical_app_id_required")
    require(re.fullmatch(r"age1[0-9a-z]{58}", recipient or "") is not None, "missing_delivery_recipient")
    require(not readiness(), "missing_or_invalid_model")
    require(os.environ.get("APPLE_ID") and os.environ.get("APPLE_PASSWORD"), "missing_apple_credentials")
    require(not output_dir.exists(), "output_directory_exists")
    progress("metadata")
    try:
        info = metadata(identifier)
    except ValueError as exc:
        status = {
            "app not found in US storefront": "app_not_found_in_us",
            "first version supports free apps only": "paid_app_not_supported",
            "metadata response exceeded budget": "metadata_response_too_large",
        }.get(str(exc), "metadata_invalid_response")
        raise ExportError(status) from None
    except (TimeoutError, urllib.error.URLError):
        raise ExportError("metadata_network_failed") from None
    check_capacity({} if requested else info, output_dir.parent)
    email = os.environ["APPLE_ID"].strip()
    # Only native downloader receives the Store password, never the delivery key.
    env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "LAB_KBSYNC_HELPER") if k in os.environ}
    env["APPLEPACKAGE_PASSWORD"] = os.environ["APPLE_PASSWORD"]
    if requested:
        env["LAB_REQUESTED_VERSION"] = requested
    login = ["login", email]
    if os.environ.get("APPLE_2FA_CODE"):
        login += ["--code", os.environ["APPLE_2FA_CODE"]]
    try:
        progress("authenticating")
        state = classify(run(binary, login, env))
        require(state == "authenticated", state)
        with tempfile.TemporaryDirectory(prefix="ipa-delivery-private-") as directory:
            root = Path(directory)
            root.chmod(0o700)
            original, candidate, cleaned = root/"source.ipa", root/"candidate.ipa", root/"delivery.ipa"
            progress("resolving_version" if requested else "downloading")
            result = run(binary, ["download", email, info["bundleId"], "--output", str(original)], env, timeout=DOWNLOAD_TIMEOUT)
            if requested and result.returncode != 0:
                markers = re.findall(r"^IPA_LAB_VERSION_ERROR:([a-z_]+)$", result.stdout or "", re.M)
                known = {"invalid_version","version_not_found","version_search_limit","version_lookup_unavailable"}
                raise ExportError(markers[-1] if markers and markers[-1] in known else "version_download_rejected")
            require(result.returncode == 0 and original.is_file(), classify_download(result))
            version_id, resolved_version = resolved_marker(result.stdout or "", requested) if requested else ("", "")
            require(0 < original.stat().st_size <= MAX_BYTES, "source_too_large")
            progress("auditing")
            before = audit(original)
            require(before["bundle_id"] == info["bundleId"], "downloaded_app_mismatch")
            verify_version(before, requested, resolved_version)
            model = root/"model.bin"
            with os.fdopen(os.open(model, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb") as stream:
                stream.write(base64.b64decode(os.environ["FAIRPLAY_MODEL_B64"], validate=True))
            child_env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG") if k in os.environ}
            child_env.update(TMPDIR=str(root), TMP=str(root), TEMP=str(root))
            report_path = root/"private-report.json"
            progress("decrypting")
            completed = subprocess.run([engine, "decrypt", "--input", str(original),
                "--output", str(candidate), "--report", str(report_path), "--model", str(model),
                "--strip-account-data"], stdin=subprocess.DEVNULL, capture_output=True,
                env=child_env, timeout=DECRYPT_TIMEOUT)
            require(completed.returncode == 0 and candidate.is_file() and report_path.is_file(),
                    "decryption_rejected")
            require(report_path.stat().st_size <= 8 * 1024 * 1024, "report_too_large")
            progress("verifying")
            report = json.loads(report_path.read_bytes())
            images, pages = validate_report(report, before, candidate)
            scrub_archive(candidate, cleaned)
            verified = verify_output(cleaned, before)
            verify_version(verified, requested, resolved_version)
            original.unlink()
            candidate.unlink()
            progress("encrypting")
            sealed = root/"package.ipa.age"
            completed = subprocess.run([crypt, "encrypt", str(cleaned), str(sealed), recipient],
                stdin=subprocess.DEVNULL, capture_output=True, env=dict(child_env, GITHUB_ACTIONS="true"),
                timeout=CRYPTO_TIMEOUT)
            require(completed.returncode == 0 and sealed.is_file(), "delivery_encryption_failed")
            receipt = {
                "schema": "ipa-private-delivery-v1", "status": "encrypted_artifact_ready",
                "request_id": request_id, "app_id": identifier,
                "requested_version": requested, "resolved_version": resolved_version,
                "external_version_id": version_id,
                "run_id": str(os.environ.get("GITHUB_RUN_ID", "")),
                "source_commit": os.environ.get("GITHUB_SHA", ""),
                "plaintext_verified": True, "runtime_verified": False,
                "account_data_removed": True, "plaintext_published": False,
                "encrypted_images": images, "decrypted_pages": pages,
                "plaintext_bytes": cleaned.stat().st_size, "plaintext_sha256": digest(cleaned),
                "ciphertext_bytes": sealed.stat().st_size, "ciphertext_sha256": digest(sealed),
                "recipient": recipient,
            }
            output_dir.mkdir(mode=0o700)
            sealed.replace(output_dir/"package.ipa.age")
            (output_dir/"receipt.json").write_text(json.dumps(receipt, sort_keys=True) + "\n")
            return {k: receipt[k] for k in ("schema", "status", "request_id", "app_id",
                    "plaintext_verified", "runtime_verified", "encrypted_images", "decrypted_pages",
                    "plaintext_bytes", "plaintext_published")}
    finally:
        try:
            run(binary, ["logout", email], env)
        except Exception:
            pass

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--binary", required=True)
    p.add_argument("--engine", required=True)
    p.add_argument("--crypt", required=True)
    args = p.parse_args()
    os.umask(0o077)
    output = Path("delivery-out")
    progress = WorkerProgress(os.environ.get("DELIVERY_REQUEST_ID",""))
    stage = "preparing"
    def advance(value):
        nonlocal stage
        stage = value
        progress.advance(value)
        # Fixed stage names only; no native output, URLs, paths or account fields.
        print(json.dumps({"schema":"ipa-export-stage-v1","stage":value}),flush=True)
    try:
        recipient = json.loads(Path("config/delivery.json").read_text())["recipient"]
        result = export(str(Path(args.binary).resolve()), str(Path(args.engine).resolve()),
                        str(Path(args.crypt).resolve()), os.environ.get("DELIVERY_APP_ID", ""),
                        os.environ.get("DELIVERY_REQUEST_ID", ""), recipient, output, advance)
        progress.advance("artifact_ready")
        print(json.dumps(result), flush=True)
        return 0
    except (ExportError, VersionError) as exc:
        status = str(exc)
    except AuditError as exc:
        status = audit_failure(exc)
    except subprocess.TimeoutExpired:
        status = "private_export_timeout"
    except Exception:
        status = "private_export_failed"
    # Only fixed failure categories become Actions outputs for bot-facing messages.
    category = ("size_limit" if status in ("source_too_large","invalid_output_size","member_too_large",
                 "macho_member_limit","audit_read_limit","archive_expansion_limit") else
                "disk_limit" if status == "insufficient_export_disk" else "")
    if category and os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"],"a") as stream:
            stream.write("capacity_failure="+category+"\n")
    version_codes = {"invalid_version","version_not_found","version_search_limit",
                     "version_lookup_unavailable","version_download_rejected",
                     "version_resolution_unconfirmed","downloaded_version_mismatch"}
    if status in version_codes and os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as stream:
            stream.write("version_failure=" + status + "\n")
    progress.advance("failed")
    # An incomplete output directory is never uploaded by the workflow.
    import shutil
    shutil.rmtree(output, ignore_errors=True)
    print(json.dumps({"schema": "ipa-private-delivery-v1", "status": status,
                      "failed_stage": stage, "plaintext_published": False}), flush=True)
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
