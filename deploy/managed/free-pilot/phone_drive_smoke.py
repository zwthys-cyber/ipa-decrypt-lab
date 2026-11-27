"""Explicit operator-run 1 KiB private Drive smoke test for iOS.

Only creates one synthetic file, retains its private journal, and checks
downloaded bytes. No sharing, deletion, Telegram registration, DRM, or CI use.
Requires a short-lived drive.file access token from the authorized account.
"""
import argparse
import getpass
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
import urllib.request
import warnings

REF = "f9aa91c54a0d81687bc45dd3d8727034391a4f50"
BASE = "https://raw.githubusercontent.com/zwthys-cyber/ipa-decrypt-lab/" + REF + "/deploy/managed/free-pilot/"
MANIFEST = {
    "private_upload.py": "1654449dc3b26f64627f2e672833c32eaea325c8",
    "archive_verify.py": "a25cb8a0348626c3332a019ee2e89b4e3325c4b7",
    "zip_preflight.py": "7df4bb0e029ccda0d4dcc713c61b580874fed9fb",
}
PREFIX = b"synthetic-phone-drive-smoke-v1\n"
SIZE = 1024


def fetch_sources(root):
    for name, expected in MANIFEST.items():
        url = BASE + name
        with urllib.request.urlopen(url, timeout=30) as response:
            if response.geturl() != url or response.status != 200:
                raise RuntimeError("source_download_unverified")
            data = response.read(131073)
        blob = hashlib.sha1(("blob " + str(len(data)) + "\0").encode("ascii") + data).hexdigest()
        if len(data) > 131072 or blob != expected:
            raise RuntimeError("source_digest_mismatch")
        (root / name).write_bytes(data)


def hidden_token():
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        return getpass.getpass("Drive Access token (hidden): ").strip()


def smoke(u, root, drive):
    root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    u.need(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
           and info.st_mode & 0o077 == 0, "smoke_directory_not_private")
    path = root / "PhoneDriveSmoke.bin"
    # A stable local file binds repeated runs to the same upload journal.
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as stream:
            stream.write(PREFIX + os.urandom(SIZE - len(PREFIX)))
            stream.flush()
            os.fsync(stream.fileno())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        stamp = u.file_snapshot(stream)
        u.need(stamp[2] == SIZE, "smoke_file_invalid")
        payload = stream.read(SIZE + 1)
        u.need(len(payload) == SIZE and payload.startswith(PREFIX), "smoke_file_invalid")
        record = u.validate_file(stream, path.name)
        job = "pilot_" + record["sha256"][:32]
        with u.Journal(root / "journal", job) as journal:
            # Read-only account/quota preflight; the existing upload module
            # also checks capacity and verifies the completed file.
            drive.check_quota(SIZE)
            print("DRIVE_ACCOUNT_AND_QUOTA_OK", flush=True)
            receipt, state = u.upload(drive, stream, record, journal, job, source_stamp=stamp)
            print("PRIVATE_UPLOAD_VERIFIED", flush=True)
            status, _, raw = drive.call("GET", u.GOOGLE + "/drive/v3/files/" + receipt["file_id"] + "?alt=media")
            u.need(status == 200 and raw == payload and hashlib.sha256(raw).hexdigest() == record["sha256"],
                   "download_integrity_unverified")
            drive.verify(record, receipt["file_id"])
            print("PRIVATE_DOWNLOAD_SHA256_OK", flush=True)
    print("PHONE_DRIVE_SMOKE_PASS", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-free-account", action="store_true")
    parser.add_argument("--confirm-synthetic-upload", action="store_true")
    args = parser.parse_args()
    if not (args.confirm_free_account and args.confirm_synthetic_upload) or os.environ.get("GITHUB_ACTIONS") == "true":
        print("OPERATOR_CONFIRMATION_REQUIRED")
        return 2
    os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="phone-drive-code-", dir=Path.cwd()) as directory:
            fetch_sources(Path(directory))
            sys.path.insert(0, directory)
            try:
                import private_upload as u
                email = input("Authorized personal Google account email: ").strip()
                token = hidden_token()
                drive = u.Drive(token, email)
                del token
                return smoke(u, Path.cwd() / ".phone-drive-smoke-v1", drive)
            except u.Stop as exc:
                print("DRIVE_SMOKE_STOP:", str(exc))
                return 2
            finally:
                sys.path.remove(directory)
    except (getpass.GetPassWarning, EOFError):
        print("DRIVE_SMOKE_STOP: hidden_input_unavailable")
        return 2
    except Exception as exc:
        print("DRIVE_SMOKE_STOP:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
