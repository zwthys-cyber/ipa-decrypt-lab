"""Bounded metadata-only observations of FairPlay state; no account login."""
import argparse
import errno
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

PATHS = {
    "fpsd_sidb": "/private/var/db/fpsd/SC Info/SC Info.sidb",
    "fpsd_sids": "/private/var/db/fpsd/SC Info/SC Info.sids",
    "shared_sidb": "/Users/Shared/SC Info/SC Info.sidb",
    "shared_sids": "/Users/Shared/SC Info/SC Info.sids",
}
STATUS = {"missing", "permission_denied", "regular_empty", "regular_nonempty", "symlink", "other_type", "unavailable"}
ROOTS = {"fpsd": "/private/var/db/fpsd", "shared": "/Users/Shared",
         "system_support": "/Library/Application Support"}
MAX_ENTRIES = 12000


def metadata(path):
    try:
        info = os.lstat(path)
    except OSError as error:
        return {"status": "missing" if error.errno in (errno.ENOENT, errno.ENOTDIR)
                else "permission_denied" if error.errno in (errno.EACCES, errno.EPERM)
                else "unavailable"}
    if stat.S_ISLNK(info.st_mode):
        status = "symlink"
    elif stat.S_ISREG(info.st_mode):
        status = "regular_nonempty" if info.st_size > 0 else "regular_empty"
    else:
        status = "other_type"
    return {"status": status}


def inventory(root, max_entries=MAX_ENTRIES, max_seconds=8):
    result = dict(sidb_files=0, sids_files=0, nonempty_sidb=0, nonempty_sids=0,
                  directories_denied=0, limit_reached=False, root_missing=False)
    pending = [(Path(root), 0)]
    visited, deadline = 0, time.monotonic() + max_seconds
    while pending:
        directory, depth = pending.pop()
        if time.monotonic() >= deadline or visited >= max_entries:
            result["limit_reached"] = True
            break
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > max_entries or time.monotonic() >= deadline:
                        result["limit_reached"] = True
                        pending.clear()
                        break
                    if entry.is_symlink():
                        continue
                    lower = entry.name.lower()
                    if entry.is_dir(follow_symlinks=False):
                        if depth < 7:
                            pending.append((Path(entry.path), depth + 1))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    kind = "sidb" if lower.endswith(".sidb") else "sids" if lower.endswith(".sids") else None
                    if kind:
                        result[kind + "_files"] += 1
                        if entry.stat(follow_symlinks=False).st_size > 0:
                            result["nonempty_" + kind] += 1
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EPERM):
                result["directories_denied"] += 1
            elif depth == 0 and error.errno in (errno.ENOENT, errno.ENOTDIR):
                result["root_missing"] = True
    return result


def snapshot():
    roots = dict(ROOTS)
    user_home = os.environ.get("HOME")
    if user_home and user_home.startswith("/Users/"):
        roots["user_support"] = str(Path(user_home) / "Library/Application Support")
        roots["user_preferences"] = str(Path(user_home) / "Library/Preferences")
    return dict(schema="ipa-lab-fairplay-state-v1", running_as_root=os.geteuid() == 0,
                files={name: metadata(path) for name, path in PATHS.items()},
                inventory={name: inventory(path) for name, path in roots.items()},
                file_contents_read=False, account_request_attempted=False)


def clean(value):
    if (type(value) is not dict or value.get("schema") != "ipa-lab-fairplay-state-v1"
            or type(value.get("running_as_root")) is not bool
            or value.get("file_contents_read") is not False
            or value.get("account_request_attempted") is not False):
        raise ValueError("invalid_observation")
    files, inventories = value.get("files"), value.get("inventory")
    if type(files) is not dict or set(files) != set(PATHS) or type(inventories) is not dict:
        raise ValueError("invalid_observation")
    sanitized = {}
    for name, item in files.items():
        if type(item) is not dict or item.get("status") not in STATUS:
            raise ValueError("invalid_observation")
        sanitized[name] = {"status": item["status"]}
    allowed = set(ROOTS) | {"user_support", "user_preferences"}
    counts = ("sidb_files", "sids_files", "nonempty_sidb", "nonempty_sids", "directories_denied")
    flags = ("limit_reached", "root_missing")
    clean_inventory = {}
    if not set(inventories) <= allowed:
        raise ValueError("invalid_observation")
    for name, item in inventories.items():
        if type(item) is not dict or any(type(item.get(k)) is not int or not 0 <= item[k] <= MAX_ENTRIES for k in counts):
            raise ValueError("invalid_observation")
        if any(type(item.get(k)) is not bool for k in flags):
            raise ValueError("invalid_observation")
        if item["nonempty_sidb"] > item["sidb_files"] or item["nonempty_sids"] > item["sids_files"]:
            raise ValueError("invalid_observation")
        clean_inventory[name] = {k: item[k] for k in counts + flags}
    return dict(schema=value["schema"], running_as_root=value["running_as_root"],
                files=sanitized, inventory=clean_inventory, file_contents_read=False,
                account_request_attempted=False)


def collect():
    from machine_enrollment import run_private
    current = clean(snapshot())
    env = {"PATH": "/usr/bin:/bin", "GITHUB_ACTIONS": "true"}
    if os.environ.get("HOME"):
        env["HOME"] = os.environ["HOME"]
    argv = ["/usr/bin/sudo", "-n", "--", "/usr/bin/env", "-i",
            "PATH=/usr/bin:/bin", "GITHUB_ACTIONS=true"]
    if "HOME" in env:
        argv.append("HOME=" + env["HOME"])
    argv += [sys.executable, str(Path(__file__).resolve()), "--snapshot"]
    report = {"current_user": current, "root_status": "unavailable"}
    try:
        code, raw, _ = run_private(argv, env, timeout=45)
        if code or len(raw) > 32768:
            return report
        root = clean(json.loads(raw))
        if not root["running_as_root"]:
            return report
        report.update(root_status="observed", root=root)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", action="store_true")
    args = parser.parse_args()
    if (os.environ.get("GITHUB_ACTIONS") != "true" or sys.platform != "darwin"
            or os.environ.get("APPLE_ID") or os.environ.get("APPLE_PASSWORD")):
        raise SystemExit("Credential-free GitHub-hosted macOS observer required")
    result = clean(snapshot()) if args.snapshot else collect()
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
