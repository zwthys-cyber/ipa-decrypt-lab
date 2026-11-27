"""Public CircleCI ARM runtime bundles. This is not a production credential adapter."""
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

SCHEMA = "circleci-native-runtime-v2"
VARIANTS = {"base", "cn", "testflight"}
BINARIES = {"ApplePackageTool", "lab-kbsync", "offline-engine", "delivery-crypt"}
RESOURCE = "ApplePackage_ApplePackage.bundle"
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_EXPANDED = 512 * 1024 * 1024
UUID = r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}"

def require(value, reason):
    if not value:
        raise ValueError(reason)

def digest(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def executable(name, variant):
    if variant == "testflight":
        return name == "tf_virtual_client" or re.fullmatch(r"libapple_auth(?:_client)?(?:\.[0-9.]+)?\.dylib", name) is not None
    return name in BINARIES

def allowed(name, variant="base"):
    p = PurePosixPath(name)
    safe = (name == p.as_posix() and not p.is_absolute() and
            all(part not in ("", ".", "..") for part in p.parts) and "\\" not in name)
    return safe and (executable(name, variant) or
                     (len(p.parts) > 1 and p.parts[0] == "licenses") or
                     (variant != "testflight" and len(p.parts) > 1 and p.parts[0] == RESOURCE))

def source_fingerprint(root):
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    hashed = hashlib.sha256()
    for raw in sorted(p for p in paths if p):
        path = Path(root) / os.fsdecode(raw)
        require(path.is_file() and not path.is_symlink(), "source_not_regular")
        hashed.update(raw + b"\0" + bytes.fromhex(digest(path)))
    return hashed.hexdigest()

def provenance(root):
    require(os.environ.get("CIRCLECI") == "true" and
            not os.environ.get("GITHUB_ACTIONS"), "circleci_required")
    require(platform.system() == "Darwin" and platform.machine() == "arm64",
            "circleci_arm_macos_required")
    version = subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()
    require(version.split(".")[0] == "26", "unsupported_macos")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    require(commit == os.environ.get("CIRCLE_SHA1") and re.fullmatch(r"[a-f0-9]{40}", commit),
            "checkout_mismatch")
    workflow = os.environ.get("CIRCLE_WORKFLOW_ID", "")
    job = os.environ.get("CIRCLE_BUILD_NUM", "")
    require(re.fullmatch(UUID, workflow) and re.fullmatch(r"[1-9][0-9]*", job),
            "invalid_circleci_identity")
    xcode = subprocess.check_output(["xcodebuild", "-version"], text=True).strip()
    swift = subprocess.check_output(["swift", "--version"], text=True).strip()
    return dict(schema=SCHEMA, platform="circleci-macos-26-arm64", commit=commit,
                workflow_id=workflow, job_number=job, macos=version, xcode=xcode,
                swift=swift, source_fingerprint=source_fingerprint(root))

def pack(root, destination, variant="base"):
    root, destination = Path(root).resolve(), Path(destination)
    require(not destination.exists(), "destination_exists")
    require(variant in VARIANTS, "invalid_variant")
    manifest = provenance(root)
    manifest["variant"] = variant
    manifest["dependencies"] = (subprocess.check_output(["brew", "list", "--versions", "mbedtls@3", "curl", "nlohmann-json", "libzip", "cmake", "ninja"], text=True).strip() if variant == "testflight" else "")
    swift = root / "native-source/ApplePackage/.build/debug"
    with tempfile.TemporaryDirectory() as temp:
        stage = Path(temp)
        if variant == "testflight":
            build = root / "tf-sdk-build"
            binaries = {p.name:p.resolve() for p in build.iterdir() if executable(p.name, variant)}
            require("tf_virtual_client" in binaries and 3 <= len(binaries) <= 19, "tf_inventory_missing")
            require(all(p.is_file() and p.is_relative_to(build.resolve()) for p in binaries.values()), "tf_library_escape")
            sources = [root / "native-source/apple-auth"]
        else:
            binaries = {name:(swift / name if name == "ApplePackageTool" else root / name) for name in BINARIES}
            require((swift / RESOURCE).is_dir(), "resource_missing")
            shutil.copytree(swift / RESOURCE, stage / RESOURCE, symlinks=True)
            sources = [root / "native-source" / name for name in ("ApplePackage", "ipatool", "unfairplay", "age")]
            sources += list((root / "native-source/ApplePackage/.build/checkouts").glob("*"))
        for name, source in binaries.items():
            require(source.is_file() and not source.is_symlink(), "binary_not_regular")
            arch = subprocess.check_output(["lipo", "-archs", str(source)], text=True).strip()
            require(arch == "arm64", "binary_architecture_mismatch")
            shutil.copyfile(source, stage / name)
            (stage / name).chmod(0o755)
        notices = stage / "licenses"
        notices.mkdir()
        if variant != "testflight":
            goroot = Path(subprocess.check_output(["go", "env", "GOROOT"], text=True).strip())
            shutil.copyfile(goroot / "LICENSE", notices / "Go-LICENSE")
            for module, target in (("ipatool", "./cmd/lab-kbsync"), ("unfairplay", "./cmd/unfairplay"), ("age", "./cmd/lab-delivery-crypt")):
                raw = subprocess.check_output(["go", "list", "-deps", "-f", "{{with .Module}}{{.Dir}}{{end}}", target],
                                              cwd=root / "native-source" / module, text=True)
                sources += [Path(p) for p in sorted(set(raw.splitlines())) if p]
        for source in sources:
            for notice in source.iterdir():
                if notice.is_file() and not notice.is_symlink() and notice.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                    shutil.copyfile(notice, notices / (source.name + "-" + notice.name))
        if variant == "testflight":
            for formula in ("mbedtls@3", "curl", "nlohmann-json", "libzip"):
                prefix = Path(subprocess.check_output(["brew", "--prefix", formula], text=True).strip())
                for notice in prefix.rglob("*"):
                    if notice.is_file() and not notice.is_symlink() and notice.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                        suffix = hashlib.sha256(notice.relative_to(prefix).as_posix().encode()).hexdigest()[:12]
                        shutil.copyfile(notice, notices / (formula + "-" + suffix + "-" + notice.name))
        files = {}
        for path in sorted(stage.rglob("*")):
            require(not path.is_symlink(), "package_symlink")
            if path.is_file():
                name = path.relative_to(stage).as_posix()
                require(allowed(name, variant), "unexpected_file")
                files[name] = dict(size=path.stat().st_size, sha256=digest(path))
        require(sum(v["size"] for v in files.values()) <= MAX_EXPANDED, "expanded_limit")
        manifest["files"] = files
        raw = json.dumps(manifest, sort_keys=True).encode()
        require(len(raw) <= 65536, "manifest_limit")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(destination, "w:gz") as archive:
            info = tarfile.TarInfo("manifest.json")
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))
            for name in files:
                archive.add(stage / name, arcname=name, recursive=False)
    require(destination.stat().st_size <= MAX_ARCHIVE, "archive_limit")
    return manifest

def unpack(archive_path, destination, expected):
    """expected must come from a separately trusted successful CircleCI job."""
    destination = Path(destination)
    variant = expected.get("variant")
    require(variant in VARIANTS, "invalid_variant")
    require(not destination.exists(), "destination_exists")
    require(Path(archive_path).stat().st_size <= MAX_ARCHIVE, "archive_limit")
    with tarfile.open(archive_path, "r:gz") as archive:
        members, names, total = [], set(), 0
        for member in archive:
            require(len(members) < 1024 and member.isfile() and not member.sparse, "invalid_entry")
            require(member.name not in names and
                    (member.name == "manifest.json" or allowed(member.name, variant)), "invalid_path")
            total += member.size
            require(0 <= member.size <= MAX_EXPANDED and total <= MAX_EXPANDED + 65536, "expanded_limit")
            names.add(member.name)
            members.append(member)
        info = next((m for m in members if m.name == "manifest.json"), None)
        require(info is not None and info.size <= 65536, "manifest_missing")
        manifest = json.load(archive.extractfile(info))
        require(isinstance(manifest, dict), "invalid_manifest")
        require(manifest.get("schema") == SCHEMA and manifest.get("platform") == "circleci-macos-26-arm64",
                "schema_or_platform_mismatch")
        require(set(expected) == {"commit", "workflow_id", "job_number", "source_fingerprint", "xcode", "swift", "macos", "variant", "dependencies"},
                "trusted_identity_required")
        require(re.fullmatch(r"[a-f0-9]{40}", expected["commit"]) and
                re.fullmatch(UUID, expected["workflow_id"]) and
                re.fullmatch(r"[1-9][0-9]*", expected["job_number"]) and
                re.fullmatch(r"[a-f0-9]{64}", expected["source_fingerprint"]), "invalid_identity")
        require(all(manifest.get(k) == v for k, v in expected.items()), "identity_or_abi_mismatch")
        files = manifest.get("files")
        require(isinstance(files, dict) and set(files) == names - {"manifest.json"} and
                (("tf_virtual_client" in files and 3 <= sum(executable(n, variant) for n in files) <= 19) if variant == "testflight" else
                 (BINARIES <= set(files) and any(n.startswith(RESOURCE + "/") for n in files))),
                "inventory_mismatch")
        destination.mkdir(parents=True)
        try:
            for member in members:
                if member.name == "manifest.json":
                    continue
                entry = files[member.name]
                require(isinstance(entry, dict) and type(entry.get("size")) is int and
                        entry["size"] == member.size and
                        re.fullmatch(r"[a-f0-9]{64}", entry.get("sha256", "")), "invalid_digest")
                path = destination / member.name
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, path.open("xb") as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                require(digest(path) == entry["sha256"], "digest_mismatch")
                path.chmod(0o755 if executable(member.name, variant) else 0o644)
        except BaseException:
            shutil.rmtree(destination)
            raise
    return manifest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["pack-and-verify"])
    parser.add_argument("--variant", choices=sorted(VARIANTS), default="base")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    variant = args.variant
    output = root / "circle-runtime-dist" / variant
    destination = output / "native-runtime.tar.gz"
    manifest = pack(root, destination, variant)
    keys = ("commit", "workflow_id", "job_number", "source_fingerprint", "xcode", "swift", "macos", "variant", "dependencies")
    unpack(destination, root / ("relocated-circle-" + variant + "-runtime"), {k: manifest[k] for k in keys})
    (destination.parent / "build-receipt.json").write_text(json.dumps(manifest, sort_keys=True) + "\n")
    print(json.dumps(dict(schema=SCHEMA, variant=variant, platform=manifest["platform"], files=len(manifest["files"]),
                          archive_sha256=digest(destination), source_fingerprint=manifest["source_fingerprint"])))

if __name__ == "__main__":
    main()
