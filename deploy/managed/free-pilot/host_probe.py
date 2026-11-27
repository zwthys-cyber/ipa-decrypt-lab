"""Offline, synthetic eligibility probe for an operator-owned foreground runtime.

No network, credentials, real archives, upload, decryption or deployment. Run
only in an app-private local directory, not a shared/cloud-synced folder.
"""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
import tempfile
import zipfile


def require(condition):
    if not condition:
        raise RuntimeError("contract_failed")


def probe(root):
    results = {}

    def check(name, fn):
        try:
            fn()
            results[name] = True
        except Exception:
            results[name] = False

    with tempfile.TemporaryDirectory(prefix="host-probe-", dir=root) as tmp:
        base = Path(tmp)
        data = base / "input.bin"
        payload = b"synthetic host probe\n"

        def private_io():
            info = base.lstat()
            require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid()
                    and info.st_mode & 0o077 == 0)
            fd = os.open(data, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
                info = os.fstat(stream.fileno())
                require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                        and info.st_mode & 0o077 == 0)
                require(isinstance(info.st_mtime_ns, int) and isinstance(info.st_ctime_ns, int))
            require(data.read_bytes() == payload)

        def nofollow():
            link = base / "link"
            link.symlink_to(data.name)
            try:
                fd = os.open(link, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError as exc:
                require(exc.errno == errno.ELOOP)
            else:
                os.close(fd)
                raise RuntimeError("followed_link")

        def locking():
            import fcntl
            with data.open("rb") as a, data.open("rb") as b:
                fcntl.flock(a.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    fcntl.flock(b.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    require(exc.errno in (errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK))
                else:
                    raise RuntimeError("lock_not_exclusive")

        def journal_io():
            new = base / "pending"
            journal = base / "journal"
            fd = os.open(new, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(new, journal)
            fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            require(journal.read_bytes() == payload and not new.exists())

        def large_seek():
            with data.open("rb") as stream:
                require(stream.seek(10_000_000_000) == 10_000_000_000)
                require(stream.read(1) == b"")
            require(data.stat().st_size == len(payload))

        def archive():
            path = base / "synthetic.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
                with z.open("synthetic.txt", "w", force_zip64=True) as member:
                    member.write(payload)
            with zipfile.ZipFile(path) as z:
                require(z.testzip() is None and z.read("synthetic.txt") == payload)
            require(hashlib.sha256(payload).digest() == hashlib.sha256(data.read_bytes()).digest())

        def tls():
            import ssl
            context = ssl.create_default_context()
            require(context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED)
            require(context.cert_store_stats().get("x509_ca", 0) > 0)

        for name, fn in (("private_file", private_io), ("no_symlink_follow", nofollow),
                         ("exclusive_lock", locking), ("durable_journal_primitives", journal_io),
                         ("large_seek_without_allocation", large_seek), ("small_zip64_member_crc_sha256", archive),
                         ("local_tls_trust_store", tls)):
            check(name, fn)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True, help="App-private local test directory")
    args = parser.parse_args(argv)
    os.umask(0o077)
    try:
        results = probe(args.directory)
    except Exception:
        print(json.dumps({"schema": "foreground-host-probe-v1", "probe_completed": False}))
        return 2
    passed = all(results.values())
    print(json.dumps({"schema": "foreground-host-probe-v1", "probe_completed": True,
                      "platform": sys.platform, "architecture": platform.machine(),
                      "python": platform.python_version(), "checks": results,
                      "synthetic_primitives_passed": passed, "live_upload_verified": False,
                      "background_runtime_verified": False, "native_decryption_verified": False}, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
