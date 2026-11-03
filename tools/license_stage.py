"""Stage only manifest-declared SINF copies in a private extracted payload."""
import plistlib
from pathlib import Path

MAX_LICENSE_BYTES = 1024 * 1024
MAX_REPLICATION_BYTES = 16 * 1024 * 1024

def relative_sinf(value):
    if (not isinstance(value, str) or not value or value.startswith("/")
            or "\\" in value or "\x00" in value):
        raise ValueError("invalid license path")
    parts = value.split("/")
    if (any(p in {"", ".", ".."} for p in parts) or len(parts) < 2
            or parts[-2] != "SC_Info" or not parts[-1].endswith(".sinf")):
        raise ValueError("invalid license path")
    return Path(*parts)

def contained(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("license path escapes bundle")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("license symlink unsupported")
    return path

def prepare(root, audit):
    bundle = root / Path(audit["main_executable"]).parent
    report = dict(manifest_present=False, replication_targets=0, replicated=0,
                  existing=0, ambiguous_sources=False, binary_sinf_present=0,
                  binary_sinf_missing=0, authorization_verified=False)
    manifest = bundle / "SC_Info" / "Manifest.plist"
    if manifest.is_file():
        report["manifest_present"] = True
        if manifest.stat().st_size > 1024 * 1024:
            raise ValueError("manifest too large")
        data = plistlib.loads(manifest.read_bytes())
        if not isinstance(data, dict):
            raise ValueError("invalid manifest")
        sources = data.get("SinfPaths", [])
        targets = data.get("SinfReplicationPaths", [])
        if not isinstance(sources, list) or not isinstance(targets, list) or len(sources) > 4096 or len(targets) > 4096:
            raise ValueError("invalid manifest lists")
        source_paths = [contained(bundle, relative_sinf(p)) for p in sources]
        target_paths = [contained(bundle, relative_sinf(p)) for p in targets]
        if len(set(target_paths)) != len(target_paths):
            raise ValueError("duplicate replication target")
        report["replication_targets"] = len(target_paths)
        source_data = []
        for source in source_paths:
            if not source.is_file() or not 0 < source.stat().st_size <= MAX_LICENSE_BYTES:
                raise ValueError("missing or oversized source license")
            source_data.append(source.read_bytes())
        # A flat replication list cannot identify which distinct source to use.
        if target_paths and (not source_data or any(value != source_data[0] for value in source_data)):
            report["ambiguous_sources"] = True
        elif target_paths:
            payload = source_data[0]
            if len(payload) * len(target_paths) > MAX_REPLICATION_BYTES:
                raise ValueError("replication budget exceeded")
            # Validate all targets before writing; never replace an existing license.
            for target in target_paths:
                if target.exists() and (not target.is_file() or target.stat().st_size > MAX_LICENSE_BYTES
                                        or target.read_bytes() != payload):
                    raise ValueError("conflicting existing license")
            for target in target_paths:
                if target.exists():
                    report["existing"] += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as output:
                    output.write(payload)
                target.chmod(0o600)
                report["replicated"] += 1
    for binary in audit["binaries"]:
        path = root / binary["path"]
        sinf = path.parent / "SC_Info" / (path.name + ".sinf")
        field = "binary_sinf_present" if sinf.is_file() and sinf.stat().st_size > 0 else "binary_sinf_missing"
        report[field] += 1
    return report
