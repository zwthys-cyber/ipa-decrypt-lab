import json
import unittest
from tf_virtual_transport_diagnostics import store_observations

class StoreShapePrivacyTests(unittest.TestCase):
    def fixture(self):
        return dict(body_bytes=100,format="xml",content_type="plist",content_encoding="missing",
            parsed=True,object=True,status_kind="integer",status_zero=True,status_code=0,status_in_range=True,
            person_id_present=True,password_token_present=True,failure_present=False,error_code_present=False,
            message_present=False,dialog_present=False,parse_failure="none")
    def encode(self,value):
        return b"TF_STORE:"+json.dumps(value).encode()
    def test_closed_metadata_is_accepted(self):
        value=self.fixture()
        self.assertEqual(store_observations(self.encode(value)),[value])
    def test_account_values_headers_and_unknown_fields_are_rejected(self):
        for key in ("body","headers","passwordToken","dsPersonId","customerMessage"):
            value=self.fixture();value[key]="PRIVATE"
            self.assertEqual(store_observations(self.encode(value)),[])
        value=self.fixture();value["content_type"]="application/PRIVATE"
        self.assertEqual(store_observations(self.encode(value)),[])
    def test_wrong_numeric_boolean_and_enum_types_are_rejected(self):
        for key,item in (("body_bytes",True),("body_bytes",16777218),("status_code","0"),
                         ("status_code",100000000),("parsed",1),("format","PRIVATE"),("parse_failure",{})):
            value=self.fixture();value[key]=item
            self.assertEqual(store_observations(self.encode(value)),[])
    def test_raw_stderr_and_observation_count_are_bounded(self):
        value=self.fixture()
        self.assertEqual(store_observations(b"PRIVATE\n"+self.encode(value)*0),[])
        self.assertEqual(len(store_observations(b"\n".join([self.encode(value)]*20))),4)
