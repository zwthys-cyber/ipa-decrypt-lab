"""Read-only integrity verification of authorized IPA and ZIP files on Linux.

No network, account access, file extraction, signing, or modification.
ZIP integrity is not a proof of authenticity, installation, or DRM status.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile
import zlib

from zip_preflight import inspect, ArchiveError, MAX_ARCHIVE, MAX_EXPANDED

CHUNK = 1024 * 1024
SHA256 = re.compile(r"[a-fA-F0-9]{64}")


class VerificationError(ValueError):
    pass


def require(ok, code):
    if not ok:
        raise VerificationError(code)


def snapshot(stream):
    info = os.fstat(stream.fileno())
    require(stat.S_ISREG(info.st_mode), "input_not_regular")
    require(info.st_uid == os.geteuid() and not info.st_mode & 0o077,
            "input_not_private")
    require(0 < info.st_size <= MAX_ARCHIVE, "archive_size_out_of_bounds")
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def verify(stream, *, ipa=False, expected=None):
    if expected is not None:
        require(isinstance(expected, str) and SHA256.fullmatch(expected),
                "invalid_expected_sha256")
    initial = snapshot(stream)
    try:
        metadata = inspect(stream)
    except ArchiveError:
        raise VerificationError("archive_structure_invalid") from None
    require(snapshot(stream) == initial, "input_changed")
    require(metadata["archive_bytes"] == initial[2], "input_changed")
    total = 0
    primary = 0
    try:
        with zipfile.ZipFile(stream, allowZip64=True) as archive:
            entries = archive.infolist()
            require(len(entries) == metadata["entries"], "input_changed")
            for item in entries:
                parts = item.filename.split("/")
                if (not item.is_dir() and len(parts) == 3 and
                        parts[0] == "Payload" and parts[1].endswith(".app") and
                        parts[1] != ".app" and parts[2] == "Info.plist" and
                        item.file_size > 0):
                    primary += 1
                size = 0
                crc = 0
                with archive.open(item) as member:
                    while True:
                        block = member.read(CHUNK)
                        if not block:
                            break
                        size += len(block)
                        total += len(block)
                        require(size <= item.file_size and total <= MAX_EXPANDED,
                                "member_size_mismatch")
                        crc = zlib.crc32(block, crc)
                require(size == item.file_size and crc == item.CRC,
                        "member_integrity_failed")
    except VerificationError:
        raise
    except (OSError, ValueError, RuntimeError, EOFError, zipfile.BadZipFile,
            zlib.error, NotImplementedError):
        raise VerificationError("member_integrity_failed") from None
    require(total == metadata["declared_expanded_bytes"], "member_size_mismatch")
    require(not ipa or primary == 1, "ipa_layout_invalid")
    require(snapshot(stream) == initial, "input_changed")
    stream.seek(0)
    digest = hashlib.sha256()
    hashed = 0
    while True:
        block = stream.read(CHUNK)
        if not block:
            break
        hashed += len(block)
        require(hashed <= initial[2], "input_changed")
        digest.update(block)
    require(hashed == initial[2] and snapshot(stream) == initial, "input_changed")
    actual = digest.hexdigest()
    require(expected is None or actual == expected.lower(), "sha256_mismatch")
    return {
        "schema": "archive-integrity-v1",
        "archive_bytes": initial[2],
        "entries": metadata["entries"],
        "expanded_bytes": total,
        "zip64": metadata["zip64"],
        "all_member_crc_verified": True,
        "sha256": actual,
        "expected_sha256_matched": expected is not None,
        "ipa_layout_present": primary == 1,
        "authenticity_verified": False,
        "installation_verified": False,
        "drm_status_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--confirm-authorized-file", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(args.confirm_authorized_file, "operator_confirmation_required")
        suffix = args.file.suffix.lower()
        require(suffix in {".ipa", ".zip"}, "unsupported_file_type")
        fd = os.open(args.file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            result = verify(stream, ipa=suffix == ".ipa",
                            expected=args.expected_sha256)
        print(json.dumps(result, sort_keys=True))
        return 0
    except VerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("archive_verification_failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
