import base64
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import private_fairplay_state as state


def packet():
    return {"schema":state.SCHEMA,"files":{"fpsd_sidb":base64.b64encode(b"SYNTHETIC_SIDB").decode()},
            "hardware":base64.b64encode(bytes(range(6))).decode()}


class StateCheckpointTests(unittest.TestCase):
    def test_valid_roundtrip_retains_exact_private_bytes(self):
        hardware,files=state.validate(json.dumps(packet()).encode())
        self.assertEqual(hardware,bytes(range(6)))
        self.assertEqual(files,{"fpsd_sidb":b"SYNTHETIC_SIDB"})

    def test_unknown_keys_and_missing_sidb_are_rejected(self):
        for value in (dict(packet(),account="PRIVATE"),dict(packet(),files={}),
                      dict(packet(),files={"../secret":"eA=="})):
            with self.assertRaises(ValueError):
                state.validate(json.dumps(value).encode())

    def test_hardware_and_file_encoding_are_strict(self):
        for hardware in ("","eA==","%%%"):
            with self.assertRaises(ValueError):
                state.validate(json.dumps(dict(packet(),hardware=hardware)).encode())
        value=packet()
        value["files"]["fpsd_sidb"]="eA==\n"
        with self.assertRaises(ValueError):
            state.validate(json.dumps(value).encode())

    def test_size_limits_are_enforced(self):
        with self.assertRaises(ValueError):
            state.validate(b"x"*(state.LIMIT+1))
        value=packet()
        value["files"]["fpsd_sidb"]=base64.b64encode(b"x"*(state.FILE_LIMIT+1)).decode()
        with self.assertRaises(ValueError):
            state.validate(json.dumps(value).encode())

    def test_materialized_files_are_private_and_fixed(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"state"
            result=state.materialize(base64.b64encode(json.dumps(packet()).encode()).decode(),root)
            self.assertEqual((result["fpsd"]/"SC Info.sidb").read_bytes(),b"SYNTHETIC_SIDB")
            for path in root.rglob("*"):
                self.assertEqual(path.stat().st_mode&0o077,0)
            self.assertEqual(result["hardware"].read_bytes(),bytes(range(6)))

    def test_invalid_packet_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"state"
            with self.assertRaises(ValueError):
                state.materialize("not base64",root)
            self.assertFalse(root.exists())

    def test_existing_destination_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"file"
            path.write_bytes(b"KEEP")
            with self.assertRaises(FileExistsError):
                state.write_private(path,b"REPLACE")
            self.assertEqual(path.read_bytes(),b"KEEP")

    def test_state_symlink_and_oversized_file_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"file"
            path.write_bytes(b"x")
            link=Path(directory)/"link"
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                state.read_state_file(link)
            path.write_bytes(b"x"*(state.FILE_LIMIT+1))
            with self.assertRaises(ValueError):
                state.read_state_file(path)
            self.assertIsNone(state.read_state_file(Path(directory)/"absent"))

    def test_hardware_requires_builtin_en0_parent(self):
        root={"IOMACAddress":bytes(range(6)),
              "IORegistryEntryChildren":[{"BSD Name":"en0","IOBuiltin":True}]}
        self.assertEqual(state.hardware_from_ioreg(plistlib.dumps([root])),bytes(range(6)))
        root["IORegistryEntryChildren"][0]["IOBuiltin"]=False
        with self.assertRaises(ValueError):
            state.hardware_from_ioreg(plistlib.dumps([root]))
        root["IORegistryEntryChildren"][0]={"BSD Name":"en1","IOBuiltin":True}
        with self.assertRaises(ValueError):
            state.hardware_from_ioreg(plistlib.dumps([root]))

    def test_capture_never_accepts_arbitrary_paths_from_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"state"
            path.write_bytes(b"SYNTHETIC_SIDB")
            hardware={"IOMACAddress":bytes(range(6)),
                      "IORegistryEntryChildren":[{"BSD Name":"en0","IOBuiltin":True}]}
            result=type("Result",(),{"returncode":0,"stdout":plistlib.dumps([hardware])})()
            with patch.object(state,"FILES",{"fpsd_sidb":str(path)}), \
                    patch.object(state.subprocess,"run",return_value=result):
                raw=state.capture()
            self.assertEqual(state.validate(raw)[1]["fpsd_sidb"],b"SYNTHETIC_SIDB")
            self.assertNotIn(str(path).encode(),raw)


if __name__=="__main__":
    unittest.main()
