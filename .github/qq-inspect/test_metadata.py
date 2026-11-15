import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from objc_metadata import Image, MetadataError

BASE = 0x100000000

def fixture(small=False, chained=False, name="QQMessageRecallModule"):
    data = bytearray(0x400)
    struct.pack_into("<8I", data, 0, 0xfeedfacf, 0x100000c, 0, 2,
                     2 if chained else 1, 168 if chained else 152, 0, 0)
    struct.pack_into("<II16sQQQQiiII", data, 32, 0x19, 152, b"__TEXT",
                     BASE, len(data), 0, len(data), 7, 5, 1, 0)
    struct.pack_into("<16s16sQQ8I", data, 104, b"__objc_classlist", b"__TEXT",
                     BASE + 0x180, 8, 0x180, 3, 0, 0, 0, 0, 0, 0)
    def ptr(offset, target):
        value = target | (1 << 51) if chained else BASE + target
        struct.pack_into("<Q", data, offset, value)
    ptr(0x180, 0x1a0)
    ptr(0x1c0, 0x1e0)
    ptr(0x1f8, 0x280)
    ptr(0x200, 0x240)
    for offset, text in ((0x280, name), (0x300, "recvSyntheticRecall:"), (0x320, "v24@0:8@16")):
        encoded = text.encode() + b"\0"
        data[offset:offset+len(encoded)] = encoded
    if small:
        struct.pack_into("<IIiii", data, 0x240, 0x8000000c, 1,
                         0x2c0 - 0x248, 0x320 - 0x24c, 0x360 - 0x250)
        ptr(0x2c0, 0x300)
    else:
        struct.pack_into("<II", data, 0x240, 24, 1)
        ptr(0x248, 0x300)
        ptr(0x250, 0x320)
        ptr(0x258, 0x360)
    if chained:
        struct.pack_into("<4I", data, 184, 0x80000034, 16, 0x380, 0x80)
        struct.pack_into("<7I", data, 0x380, 0, 28, 0, 0, 0, 0, 0)
        struct.pack_into("<II", data, 0x39c, 1, 8)
        struct.pack_into("<IHHQIHH", data, 0x3a4, 24, 4096, 6, 0, 0, 1, 0xffff)
    return data

class MetadataTests(unittest.TestCase):
    def test_big_and_relative_methods_with_and_without_chained_pointers(self):
        for small in (False, True):
            for chained in (False, True):
                with self.subTest(small=small, chained=chained):
                    self.assertEqual(Image(fixture(small, chained)).inspect(), [{
                        "class": "QQMessageRecallModule", "class_method": False,
                        "selector": "recvSyntheticRecall:", "types": "v24@0:8@16",
                        "imp": hex(BASE + 0x360),
                    }])
    def test_unselected_class_is_not_exported(self):
        self.assertEqual(Image(fixture(name="UnrelatedClass")).inspect(), [])
    def test_invalid_stride_is_rejected(self):
        data = fixture()
        struct.pack_into("<I", data, 0x240, 20)
        with self.assertRaises(MetadataError):
            Image(data).inspect()
    def test_truncated_image_is_rejected(self):
        with self.assertRaises(MetadataError):
            Image(fixture()[:0x200])
    def test_unsupported_chained_format_is_rejected(self):
        data = fixture(chained=True)
        struct.pack_into("<H", data, 0x3a4 + 6, 14)
        with self.assertRaises(MetadataError):
            Image(data).inspect()
    def test_unmapped_selector_is_rejected(self):
        data = fixture()
        struct.pack_into("<Q", data, 0x248, 0x999999999)
        with self.assertRaises(MetadataError):
            Image(data).inspect()

if __name__ == "__main__":
    unittest.main()
