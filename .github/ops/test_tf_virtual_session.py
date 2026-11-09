import json
import unittest
from tf_virtual_transport_diagnostics import session_observations

class SavedSessionPrivacyTests(unittest.TestCase):
    def fixture(self):
        return {"parsed":True,"id_matches":True,"pet_matches":True,"expiry_kind":"integer",
                "remaining_seconds":-200,"has_root_key":True,"has_root_challenge":True,"has_idms_token":True}

    def test_only_closed_account_summary_can_be_published(self):
        value=self.fixture()
        self.assertEqual(session_observations(b"TF_SESSION:"+json.dumps(value).encode()),[value])
        value["pet"]="PRIVATE"
        self.assertEqual(session_observations(b"TF_SESSION:"+json.dumps(value).encode()),[])

    def test_types_and_ranges_are_strict(self):
        for key,value in (("remaining_seconds",True),("remaining_seconds",100000),("expiry_kind","PRIVATE")):
            candidate=self.fixture();candidate[key]=value
            self.assertEqual(session_observations(b"TF_SESSION:"+json.dumps(candidate).encode()),[])
