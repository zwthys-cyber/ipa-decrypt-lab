"""Read selected ObjC class method metadata from a thin little-endian Mach-O.
No image loading or instruction execution. Format references: Apple's objc4
objc-runtime-new.h and dyld include/mach-o/fixup-chains.h.
"""
import mmap
import re
import struct

SELECTED = re.compile(r".*(?:Recall|Revoke|NTAIOFloatEar|OCMsgRecord|KTIKernelMsgListener|QQNewSettings).*")

SELECTOR = re.compile(r"recall|revoke|onMsgDelete|onMsgInfoList|onRecvMsg", re.I)

class MetadataError(ValueError):
    pass

class Image:
    def __init__(self, data):
        self.data = data
        self.segments = []
        self.sections = []
        self.formats = {}
        self.fixups = None
        self.require(data[:4] == b"\xcf\xfa\xed\xfe", "requires thin little-endian Mach-O 64")
        commands, command_bytes = self.unpack("<II", 16)
        self.require(commands <= 4096 and 32 + command_bytes <= len(data), "invalid load commands")
        offset = 32
        for _ in range(commands):
            cmd, size = self.unpack("<II", offset)
            self.require(size >= 8 and offset + size <= 32 + command_bytes, "invalid load command size")
            if cmd == 0x19:
                self.require(size >= 72, "short segment")
                vm, vs, fo, fs = self.unpack("<QQQQ", offset + 24)
                self.require(fo + fs <= len(data), "segment beyond file")
                self.segments.append((vm, fs, fo))
                count, = self.unpack("<I", offset + 64)
                self.require(72 + count * 80 <= size, "invalid sections")
                for i in range(count):
                    p = offset + 72 + i * 80
                    name = data[p:p+16].split(b"\0")[0].decode("ascii")
                    address, length = self.unpack("<QQ", p + 32)
                    self.sections.append((name, address, length))
            elif cmd == 0x80000034:
                self.require(size >= 16, "short fixups command")
                self.fixups, length = self.unpack("<II", offset + 8)
                self.require(self.fixups + length <= len(data), "fixups beyond file")
            offset += size
        self.require(offset == 32 + command_bytes, "load command byte count mismatch")
        bases = [vm for vm, fs, fo in self.segments if fo == 0 and fs]
        self.require(len(bases) == 1, "ambiguous image base")
        self.base = bases[0]
        if self.fixups is not None:
            starts, = self.unpack("<I", self.fixups + 4)
            table = self.fixups + starts
            count, = self.unpack("<I", table)
            self.require(count <= len(self.segments), "invalid fixup segment count")
            for i in range(count):
                relative, = self.unpack("<I", table + 4 + i * 4)
                if relative:
                    form, = self.unpack("<H", table + relative + 6)
                    self.formats[i] = form

    @staticmethod
    def require(condition, message):
        if not condition:
            raise MetadataError(message)

    def unpack(self, fmt, offset):
        self.require(0 <= offset and offset + struct.calcsize(fmt) <= len(self.data), "read beyond file")
        return struct.unpack_from(fmt, self.data, offset)

    def location(self, address, size=1):
        for index, (vm, fs, fo) in enumerate(self.segments):
            if vm <= address and address + size <= vm + fs:
                return fo + address - vm, index
        raise MetadataError("unmapped virtual address")

    def integer(self, address, fmt):
        offset, _ = self.location(address, struct.calcsize(fmt))
        return self.unpack(fmt, offset)[0]

    def pointer(self, address):
        offset, segment = self.location(address, 8)
        raw, = self.unpack("<Q", offset)
        if not raw:
            return 0
        form = self.formats.get(segment)
        if form is None:
            return raw
        if form in (2, 6):
            if raw >> 63:  # external symbol binding
                return 0
            target = (raw & ((1 << 36) - 1)) | (((raw >> 36) & 255) << 56)
            return target + (self.base if form == 6 else 0)
        if form in (1, 9, 12):
            if (raw >> 62) & 1:
                return 0
            if raw >> 63:
                return self.base + (raw & 0xffffffff)
            target = (raw & ((1 << 43) - 1)) | (((raw >> 43) & 255) << 56)
            return target + (self.base if form in (9, 12) else 0)
        raise MetadataError("unsupported chained pointer format")

    def string(self, address):
        offset, segment = self.location(address)
        vm, fs, fo = self.segments[segment]
        limit = min(offset + 2048, fo + fs)
        end = self.data.find(b"\0", offset, limit)
        self.require(end >= offset, "unterminated metadata string")
        try:
            result = self.data[offset:end].decode("ascii")
        except UnicodeError:
            raise MetadataError("non-ASCII metadata string") from None
        self.require(result and all(32 <= ord(c) < 127 for c in result), "invalid metadata string")
        return result

    def methods(self, address, class_name, is_meta):
        if not address:
            return []
        self.require(not address & 1, "relative list-of-lists unsupported")
        flags = self.integer(address, "<I")
        count = self.integer(address + 4, "<I")
        small = bool(flags & 0x80000000)
        direct = bool(flags & 0x40000000)
        stride = flags & 0xfffc
        self.require(stride == (12 if small else 24) and count < 100000, "invalid method list")
        output = []
        for i in range(count):
            p = address + 8 + i * stride
            if small:
                name = p + self.integer(p, "<i")
                if not direct:
                    name = self.pointer(name)
                types = p + 4 + self.integer(p + 4, "<i")
                imp = p + 8 + self.integer(p + 8, "<i")
            else:
                name, types, imp = self.pointer(p), self.pointer(p + 8), self.pointer(p + 16)
            selector = self.string(name)
            if not SELECTED.fullmatch(class_name) and not SELECTOR.search(selector):
                continue
            encoding = self.string(types)
            output.append({"class": class_name, "class_method": is_meta,
                           "selector": selector, "types": encoding, "imp": hex(imp)})
        return output

    def inspect(self):
        result = []
        for section, address, size in self.sections:
            if section != "__objc_classlist":
                continue
            self.require(size % 8 == 0 and size // 8 < 100000, "invalid class list")
            for position in range(address, address + size, 8):
                cls = self.pointer(position)
                if not cls:
                    continue
                ro = self.pointer(cls + 32) & ~7
                name = self.string(self.pointer(ro + 24))
                result.extend(self.methods(self.pointer(ro + 32), name, False))
                meta = self.pointer(cls)
                if meta:
                    meta_ro = self.pointer(meta + 32) & ~7
                    result.extend(self.methods(self.pointer(meta_ro + 32), name, True))
        for section, address, size in self.sections:
            if section != "__objc_catlist":
                continue
            self.require(size % 8 == 0, "invalid category list")
            for position in range(address, address + size, 8):
                cat = self.pointer(position)
                cls = self.pointer(cat + 8)
                if not cls:
                    continue  # category on an external class cannot be resolved here
                ro = self.pointer(cls + 32) & ~7
                name = self.string(self.pointer(ro + 24))
                category = self.string(self.pointer(cat))
                for is_meta, offset in ((False, 16), (True, 24)):
                    entries = self.methods(self.pointer(cat + offset), name, is_meta)
                    for entry in entries:
                        entry["category"] = category
                    result.extend(entries)
        return result

def inspect(path):
    with open(path, "rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        return Image(data).inspect()
