import copy
import unittest
from tf_virtual_cookie_inspect import validate
class CookieInspectionPrivacyTests(unittest.TestCase):
    def fixture(self):
        flags=dict(count=1,name_bad=0,value_bad=0,domain_bad=0,path_bad=0,expiry_kind_bad=0,host_flag_kind_bad=0)
        return dict(schema="tf-cookie-inspection-v1",before=flags,after=copy.deepcopy(flags),
            original_failure="invalid_saved_cookie",response_binding=True,network_requests=0)
    def test_fixed_summary_accepted(self):
        self.assertEqual(validate(self.fixture())["network_requests"],0)
    def test_private_values_and_raw_errors_rejected(self):
        for key in ("cookies","headers","error","body","token"):
            value=self.fixture();value[key]="PRIVATE"
            with self.assertRaises(ValueError):validate(value)
        value=self.fixture();value["original_failure"]="PRIVATE"
        with self.assertRaises(ValueError):validate(value)
    def test_counts_and_network_proof_strict(self):
        for key,item in (("count",True),("count",257),("domain_bad",2),("path_bad",-1)):
            value=self.fixture();value["before"][key]=item
            with self.assertRaises(ValueError):validate(value)
        for key,item in (("network_requests",True),("network_requests",1),("response_binding",1)):
            value=self.fixture();value[key]=item
            with self.assertRaises(ValueError):validate(value)
