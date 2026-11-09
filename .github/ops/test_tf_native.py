import unittest
from tf_native_check import validate

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
