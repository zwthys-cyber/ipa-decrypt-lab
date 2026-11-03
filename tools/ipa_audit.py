"""Read-only IPA structural audit. Does not decrypt, extract, or validate plaintext."""
import argparse
import json
from pathlib import PurePosixPath
import plistlib
import stat
import struct
import sys
import zipfile

MEMBER_LIMIT = 128 * 1024 * 1024
READ_LIMIT = 512 * 1024 * 1024
ENTRY_LIMIT = 4096
MAGICS = {
    b"\xce\xfa\xed\xfe": ("<", 28),
    b"\xcf\xfa\xed\xfe": ("<", 32),
    b"\xfe\xed\xfa\xce": (">", 28),
    b"\xfe\xed\xfa\xcf": (">", 32),
}
FAT_MAGICS = {
    b"\xca\xfe\xba\xbe": (">", False),
    b"\xbe\xba\xfe\xca": ("<", False),
    b"\xca\xfe\xba\xbf": (">", True),
    b"\xbf\xba\xfe\xca": ("<", True),
}

class AuditError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise AuditError(message)

def thin(data):
    require(data[:4] in MAGICS, "unsupported or invalid Mach-O magic")
    endian, header_size = MAGICS[data[:4]]
    require(len(data) >= header_size, "truncated Mach-O header")
    cpu, subtype = struct.unpack_from(endian + "II", data, 4)
    count, command_bytes = struct.unpack_from(endian + "II", data, 16)
    require(command_bytes <= len(data) - header_size, "commands outside image")
    require(count <= command_bytes // 8, "invalid command count")
    end, off = header_size + command_bytes, header_size
    encryption = None
    for _ in range(count):
        require(off + 8 <= end, "truncated load command")
        cmd, size = struct.unpack_from(endian + "II", data, off)
        require(size >= 8 and size % (8 if header_size == 32 else 4) == 0 and size <= end - off,
                "invalid load command size")
        if cmd in (0x21, 0x2C):
            require(encryption is None, "duplicate encryption command")
            require(cmd == (0x2C if header_size == 32 else 0x21), "encryption command/header mismatch")
            require(size == (24 if cmd == 0x2C else 20), "invalid encryption command")
            cryptoff, cryptsize, cryptid = struct.unpack_from(endian + "III", data, off + 8)
            require(cryptoff <= len(data) and cryptsize <= len(data) - cryptoff, "encryption outside image")
            require(not cryptid or (cryptsize > 0 and cryptoff >= end), "encrypted range overlaps header")
            encryption = {"cryptid": cryptid, "offset": cryptoff, "size": cryptsize}
        off += size
    require(off == end, "load command length mismatch")
    return {"cpu_type": cpu, "cpu_subtype": subtype,
            "encryption": encryption, "runtime_verified": False}

def macho(data):
    if data[:4] not in FAT_MAGICS:
        return [thin(data)]
    endian, wide = FAT_MAGICS[data[:4]]
    require(len(data) >= 8, "truncated FAT header")
    count = struct.unpack_from(endian + "I", data, 4)[0]
    stride = 32 if wide else 20
    table_end = 8 + count * stride
    require(0 < count <= 32 and table_end <= len(data), "invalid FAT architecture table")
    ranges, slices = [], []
    for index in range(count):
        at = 8 + index * stride
        cpu, subtype = struct.unpack_from(endian + "II", data, at)
        offset, size = struct.unpack_from(endian + ("QQ" if wide else "II"), data, at + 8)
        alignment = struct.unpack_from(endian + "I", data, at + (24 if wide else 16))[0]
        require(alignment <= 31 and offset % (1 << alignment) == 0, "invalid FAT alignment")
        require(offset >= table_end and size > 0 and offset <= len(data) and size <= len(data) - offset,
                "FAT slice outside file or overlaps table")
        require(all(offset + size <= start or offset >= stop for start, stop in ranges), "overlapping FAT slices")
        ranges.append((offset, offset + size))
        parsed = thin(data[offset:offset + size])
        require(parsed["cpu_type"] == cpu and parsed["cpu_subtype"] == subtype, "FAT architecture mismatch")
        parsed["fat_offset"] = offset
        slices.append(parsed)
    return slices

def audit(path):
    read_bytes = 0
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        require(len(entries) <= ENTRY_LIMIT, "archive entry limit exceeded")
        names = set()
        for entry in entries:
            name = entry.filename
            parts = name.rstrip("/").split("/")
            require(name and not name.startswith("/") and "\\" not in name and "\x00" not in name and
                    all(p not in ("", ".", "..") for p in parts), "unsafe archive path")
            require(name not in names, "duplicate archive path")
            names.add(name)
            require(not stat.S_ISLNK(entry.external_attr >> 16), "symlink entries unsupported")
            require(not entry.flag_bits & 1, "password-protected ZIP unsupported")
        roots = [n for n in names if n.startswith("Payload/") and n.count("/") == 2
                 and n.endswith(".app/Info.plist")]
        require(len(roots) == 1, "expected exactly one root application Info.plist")
        info_entry = archive.getinfo(roots[0])
        require(info_entry.file_size <= 1024 * 1024, "Info.plist size limit exceeded")
        info = plistlib.loads(archive.read(info_entry))
        require(isinstance(info, dict), "invalid Info.plist")
        executable = info.get("CFBundleExecutable")
        require(isinstance(executable, str) and executable not in ("", ".", "..") and
                "/" not in executable and "\\" not in executable, "invalid executable name")
        main_path = roots[0].rsplit("/", 1)[0] + "/" + executable
        require(main_path in names, "root executable missing")
        binaries = []
        for entry in entries:
            if entry.is_dir() or not entry.filename.startswith("Payload/"):
                continue
            with archive.open(entry) as stream:
                magic = stream.read(4)
                read_bytes += len(magic)
                if magic not in MAGICS and magic not in FAT_MAGICS:
                    continue
                require(entry.file_size <= MEMBER_LIMIT, "Mach-O member size limit exceeded")
                require(read_bytes + entry.file_size <= READ_LIMIT, "audit read budget exceeded")
                data = magic + stream.read(MEMBER_LIMIT + 1)
                read_bytes += len(data) - len(magic)
            require(len(data) == entry.file_size and len(data) <= MEMBER_LIMIT, "member length mismatch")
            binaries.append({"path": entry.filename, "slices": macho(data)})
        require(any(b["path"] == main_path for b in binaries), "root executable is not a supported Mach-O")
        encrypted = sum(1 for b in binaries for s in b["slices"]
                        if s["encryption"] is not None and s["encryption"]["cryptid"] != 0)
        return {
            "bundle_id": info.get("CFBundleIdentifier"),
            "version": info.get("CFBundleShortVersionString"),
            "minimum_os": info.get("MinimumOSVersion"),
            "main_executable": main_path,
            "binary_count": len(binaries),
            "encrypted_slice_count": encrypted,
            "status": "encrypted_slices_present" if encrypted else "no_encrypted_flags_found",
            "plaintext_verified": False,
            "runtime_verified": False,
            "whole_archive_crc_verified": False,
            "binaries": binaries,
        }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ipa")
    args = parser.parse_args()
    try:
        result = audit(args.ipa)
    except (AuditError, OSError, zipfile.BadZipFile, plistlib.InvalidFileException,
            RuntimeError, ValueError, EOFError, NotImplementedError) as exc:
        print(json.dumps({"status": "invalid_or_unsupported", "error": str(exc)}))
        return 2
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
