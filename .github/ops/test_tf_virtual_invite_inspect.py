import json
import unittest
from tf_virtual_invite_inspect import summarize
class InvitationInspectionTests(unittest.TestCase):
    def test_no_raw_values_or_unrecognized_dynamic_keys(self):
        value=summarize({"app":{"name":"PRIVATE_NAME","bundleId":"PRIVATE_BUNDLE","status":"PRIVATE_STATUS","PRIVATE_KEY":"PRIVATE_TOKEN"}},[])
        self.assertNotIn("PRIVATE",json.dumps(value))
        self.assertEqual(value["states"],["OTHER"])
        self.assertFalse(value["acceptance_attempted"])
    def test_membership_requires_binding_not_name(self):
        value=summarize({"app":{"name":"A.I.","bundleId":"example.fixture"}},[{"name":"A.I.","bundleId":"different.fixture"}])
        self.assertTrue(value["target_name_matches"]);self.assertFalse(value["catalog_app_binding_match"])
        self.assertTrue(summarize({"bundleId":"example.fixture"},[{"bundleId":"example.fixture"}])["catalog_app_binding_match"])
    def test_boolean_types_are_not_coerced(self):
        value=summarize({"isAccepted":1,"requiresAgreement":True,"status":"INVITED"},[])
        self.assertNotIn("isAccepted",value["flags"])
        self.assertEqual(value["flags"]["requiresAgreement"],[True])
        self.assertEqual(value["states"],["INVITED"])
