import unittest
from tf_native_check import validate, summarize_probe
import subprocess
import json

class NativeTFPrivacyTests(unittest.TestCase):
    def fixture(self):
        return {"schema":"testflight-native-preflight-v1","status":"ready","native_udid_20":True,
                "native_mac_model":True,"native_machine_header":True,"native_identifier_length":40,
                "hardware_source":"authkit_unique_identifier","private_profile_written":False}
    def test_accepts_only_complete_native_context(self):
        self.assertEqual(validate(self.fixture())["status"],"ready")
        value=self.fixture();value["native_udid_20"]=False
        with self.assertRaises(ValueError):validate(value)
    def test_identity_and_header_material_cannot_enter_public_report(self):
        for key in ("udid","serial","headers","sessionId","email"):
            value=self.fixture();value[key]="PRIVATE_MATERIAL"
            with self.assertRaises(ValueError):validate(value)
    def test_boolean_and_enum_types_are_strict(self):
        for key,value in (("native_identifier_length",True),("native_udid_20",1),("status","PRIVATE"),("hardware_source","fabricated")):
            data=self.fixture();data[key]=value
            with self.assertRaises(ValueError):validate(data)

    def test_signal_is_distinguished_without_publishing_stderr(self):
        result = subprocess.CompletedProcess([], -6, b"", b"PRIVATE_ACCOUNT\nTF_PROBE_STAGE:headers\n")
        value, category, info = summarize_probe(result)
        self.assertIsNone(value)
        self.assertEqual(category, "process_signal")
        self.assertEqual(info, {"exit_code": -6, "stdout_bytes": 0, "stage": "headers"})
        self.assertNotIn("PRIVATE", str(info))

    def test_invalid_output_and_schema_are_distinguished(self):
        for payload, expected in ((b"private-noise", "invalid_json"), (b"{}", "invalid_report"),
                                  (b"x" * 2049, "output_too_large")):
            value, category, info = summarize_probe(subprocess.CompletedProcess([], 2, payload, b""))
            self.assertIsNone(value)
            self.assertEqual(category, expected)
            self.assertEqual(info["stage"], "not_started")

    def test_valid_probe_preserves_native_failure(self):
        value, category, _ = summarize_probe(subprocess.CompletedProcess(
            [], 0, json.dumps(self.fixture()).encode(), b"TF_PROBE_STAGE:finished\n"))
        self.assertEqual(category, "valid_report")
        self.assertEqual(value, self.fixture())
