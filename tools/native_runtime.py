"""Credential-free native runtime packaging and authenticated Actions artifact loading."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

WORKFLOW = ".github/workflows/native-runtime-build.yml"
SCHEMA = "native-runtime-v1"
BINARIES = {"ApplePackageTool", "lab-kbsync", "offline-engine", "delivery-crypt"}
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
RESOURCE = "ApplePackage_ApplePackage.bundle"

def require(value, reason):
    if not value:
        raise ValueError(reason)

def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def fingerprint(root):
    root = Path(root)
    paths = [root / WORKFLOW]
    for directory in ("tools", "tests"):
        paths.extend(p for p in (root / directory).rglob("*")
                     if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
    hashed = hashlib.sha256()
    for path in sorted(paths):
        require(not path.is_symlink(), "source_symlink")
        hashed.update(path.relative_to(root).as_posix().encode() + b"\0")
        hashed.update(bytes.fromhex(digest(path)))
    return hashed.hexdigest()

def host_pool():
    require(platform.system() == "Darwin" and platform.machine() == "x86_64", "unsupported_runtime_host")
    major = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip().split(".")[0]
    require(major in ("15", "26"), "unsupported_runtime_os")
    return "macos-" + major + "-intel"

def allowed(name):
    p = PurePosixPath(name)
    return (name == p.as_posix() and not p.is_absolute() and
            all(part not in ("", ".", "..") for part in p.parts) and
            "\\" not in name and
            (name in BINARIES or
             (len(p.parts) > 1 and p.parts[0] in (RESOURCE, "licenses"))))

def pack(root, destination):
    root, destination = Path(root).resolve(), Path(destination)
    require(not destination.exists(), "package_destination_exists")
    pool = host_pool()
    swift = root / "native-source/ApplePackage/.build/debug"
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        for name in BINARIES:
            source = swift / name if name == "ApplePackageTool" else root / name
            shutil.copyfile(source, stage / name)
            (stage / name).chmod(0o755)
        require((swift / RESOURCE).is_dir(), "swift_resources_missing")
        shutil.copytree(swift / RESOURCE, stage / RESOURCE)
        licenses = stage / "licenses"
        licenses.mkdir()
        # Include notices for all checked-out direct and transitive sources.
        sources = [root / "native-source" / name for name in ("ApplePackage", "ipatool", "unfairplay", "age")]
        sources += list((root / "native-source/ApplePackage/.build/checkouts").glob("*"))
        for source in sources:
            for notice in source.iterdir():
                if notice.is_file() and notice.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                    shutil.copyfile(notice, licenses / (source.name + "-" + notice.name))
        files = {}
        for path in sorted(stage.rglob("*")):
            require(not path.is_symlink(), "package_symlink")
            if path.is_file():
                name = path.relative_to(stage).as_posix()
                require(allowed(name), "unexpected_package_file")
                files[name] = {"size": path.stat().st_size, "sha256": digest(path)}
        require(sum(v["size"] for v in files.values()) <= MAX_EXPANDED, "package_too_large")
        manifest = dict(schema=SCHEMA, fingerprint=fingerprint(root), pool=pool,
                        commit=os.environ["GITHUB_SHA"], run_id=os.environ["GITHUB_RUN_ID"], files=files)
        raw = json.dumps(manifest, sort_keys=True).encode()
        require(len(raw) <= 65536, "manifest_too_large")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(destination, "w:gz") as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            for name in files:
                archive.add(stage / name, arcname=name, recursive=False)
    require(destination.stat().st_size <= MAX_ARCHIVE, "archive_too_large")
    print(json.dumps({"fingerprint":manifest["fingerprint"], "pool":pool,
                      "bytes":destination.stat().st_size, "files":len(files)}))

def unpack(archive_path, destination, expected_fingerprint, pool, commit=None, run_id=None):
    destination = Path(destination)
    require(not destination.exists(), "runtime_destination_exists")
    require(Path(archive_path).stat().st_size <= MAX_ARCHIVE, "archive_too_large")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = []
        total = 0
        names = set()
        for member in archive:
            require(len(members) < 1024 and member.isfile() and not member.sparse,
                    "invalid_archive_entry")
            require(member.name not in names and
                    (member.name == "manifest.json" or allowed(member.name)), "invalid_archive_path")
            names.add(member.name)
            total += member.size
            require(0 <= member.size <= MAX_EXPANDED and total <= MAX_EXPANDED + 65536, "expanded_limit")
            members.append(member)
        info = next((m for m in members if m.name == "manifest.json"), None)
        require(info is not None and info.size <= 65536, "manifest_missing_or_large")
        manifest = json.load(archive.extractfile(info))
        require(manifest.get("schema") == SCHEMA and manifest.get("fingerprint") == expected_fingerprint
                and manifest.get("pool") == pool, "runtime_source_or_platform_mismatch")
        require(re.fullmatch("[a-f0-9]{40}", manifest.get("commit", "")) and
                re.fullmatch("[1-9][0-9]*", manifest.get("run_id", "")), "invalid_provenance")
        require(commit is None or manifest["commit"] == commit, "runtime_commit_mismatch")
        require(run_id is None or manifest["run_id"] == str(run_id), "runtime_run_mismatch")
        files = manifest.get("files")
        require(isinstance(files, dict) and set(files) == names - {"manifest.json"}
                and BINARIES <= set(files) and any(n.startswith(RESOURCE + "/") for n in files),
                "runtime_inventory_mismatch")
        destination.mkdir(parents=True)
        try:
            for member in members:
                if member.name == "manifest.json":
                    continue
                expected = files[member.name]
                require(isinstance(expected, dict) and expected.get("size") == member.size
                        and re.fullmatch("[a-f0-9]{64}", expected.get("sha256", "")), "invalid_file_digest")
                target = destination / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, target.open("xb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                require(digest(target) == expected["sha256"], "runtime_digest_mismatch")
                target.chmod(0o755 if member.name in BINARIES else 0o644)
            (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
        except BaseException:
            shutil.rmtree(destination)
            raise
    return manifest

def trusted_run(run, artifact):
    return (run.get("path") == WORKFLOW and run.get("head_branch") == "main"
            and run.get("event") in ("push", "workflow_dispatch", "schedule")
            and run.get("status") == "completed" and run.get("conclusion") == "success"
            and run.get("id") == artifact.get("workflow_run", {}).get("id")
            and run.get("head_sha") == artifact.get("workflow_run", {}).get("head_sha"))

def fetch(root, destination):
    from telegram_queue import GitHub
    client = GitHub(os.environ.get("GH_TOKEN", ""))
    pool, stamp = host_pool(), fingerprint(root)
    name = "runtime-" + pool + "-" + stamp
    artifacts = client.call("/actions/artifacts?per_page=20&name=" + name).get("artifacts", [])
    found = None
    for item in artifacts:
        if item.get("name") != name or item.get("expired") is not False:
            continue
        run_id = item.get("workflow_run", {}).get("id")
        if type(run_id) is not int or run_id <= 0:
            continue
        run = client.call("/actions/runs/" + str(run_id))
        if trusted_run(run, item):
            found = item, run
            break
    require(found is not None, "validated_runtime_missing: run native-runtime-build.yml for this source")
    item, run = found
    require(type(item.get("size_in_bytes")) is int and 0 < item["size_in_bytes"] <= MAX_ARCHIVE,
            "runtime_artifact_size")
    require(re.fullmatch("sha256:[a-f0-9]{64}", item.get("digest", "")), "artifact_digest_missing")
    with tempfile.TemporaryDirectory(prefix="native-runtime-") as temp:
        archive = Path(temp) / "artifact.zip"
        client.archive(item["id"], archive, max_bytes=MAX_ARCHIVE)
        require("sha256:" + digest(archive) == item["digest"], "artifact_digest_mismatch")
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            require(len(entries) == 1 and entries[0].filename == "native-runtime.tar.gz"
                    and 0 < entries[0].file_size <= MAX_ARCHIVE, "runtime_zip_inventory")
            packed = Path(temp) / "native-runtime.tar.gz"
            with zipped.open(entries[0]) as source, packed.open("xb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
        unpack(packed, destination, stamp, pool, run["head_sha"], run["id"])
    print(json.dumps({"runtime_run":run["id"], "pool":pool, "fingerprint":stamp,
                      "archive_bytes":item["size_in_bytes"]}))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("fingerprint", "pack", "verify", "fetch"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="runtime")
    parser.add_argument("--archive", default="runtime-out/native-runtime.tar.gz")
    args = parser.parse_args()
    if args.mode == "fingerprint":
        print(fingerprint(args.root))
    elif args.mode == "pack":
        pack(args.root, args.archive)
    elif args.mode == "verify":
        unpack(args.archive, args.output, fingerprint(args.root), host_pool(),
               os.environ["GITHUB_SHA"], os.environ["GITHUB_RUN_ID"])
    else:
        fetch(args.root, args.output)

if __name__ == "__main__":
    main()
