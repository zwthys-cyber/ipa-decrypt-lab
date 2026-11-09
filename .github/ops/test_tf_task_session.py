import base64
import copy
import json
import unittest
from tf_task_session import validated,ORIGIN_RUN,ORIGIN_SOURCE
class SavedTFSession(unittest.TestCase):
    def fixture(self):
        return {"schema":"tf-saved-session-v1","profile":{"schema":"testflight-virtual-profile-v1","origin":"independent_sdk_virtual_identity",
            "run_id":ORIGIN_RUN,"source_commit":ORIGIN_SOURCE,"hardware20":"a"*40},"context":{"accountId":"SYNTHETIC","sessionId":"SYNTHETIC",
            "dsid":"12345","udid":"a"*40,"deviceVendorId":"SYNTHETIC","deviceName":"Synthetic virtual Mac","deviceModel":"Mac14,7",
            "headers":{"X-Apple-AMD-M":"SYNTHETIC","X-Apple-Store-Front":"143465-1,29"}},"sdk_state":{"identity.json":base64.b64encode(b"SYNTHETIC").decode()}}
    def test_exact_origin_identity_and_context_are_required(self):
        validated(self.fixture())
        for section,key,item in (("profile","run_id","1"),("context","udid","b"*40),("context","deviceModel","iPhone18,2"),
                ("context","sessionId",""),("context","dsid","not-an-id")):
            value=self.fixture();value[section][key]=item
            with self.assertRaises(ValueError):validated(value)
    def test_forbidden_root_material_and_unsafe_sdk_path_are_rejected(self):
        value=self.fixture();value["gsa_password"]="PRIVATE"
        with self.assertRaises(ValueError):validated(value)
        value=self.fixture();value["sdk_state"]["../PRIVATE"]=base64.b64encode(b"SYNTHETIC").decode()
        with self.assertRaises(ValueError):validated(value)
        value=self.fixture();value["context"]["headers"]["Unexpected"]="PRIVATE"
        with self.assertRaises(ValueError):validated(value)
