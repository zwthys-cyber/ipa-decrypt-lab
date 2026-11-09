import json
from pathlib import Path
import unittest
from tf_virtual_auth_patch import patch
from tf_virtual_transport_diagnostics import verification_observations

class AuthenticationPatchTests(unittest.TestCase):
    def test_unpinned_auth_source_is_rejected(self):
        with self.assertRaises(ValueError):patch(b"unreviewed authentication source")

    def test_verification_shape_cannot_expose_raw_reply_or_code(self):
        value={"envelope":"response","object":True,"ec_present":True,"ec_integer":True,"ec_in_range":True,"ec_code":0}
        self.assertEqual(verification_observations(b"TF_VERIFY:"+json.dumps(value).encode()),[value])
        value["code"]="123456"
        self.assertEqual(verification_observations(b"TF_VERIFY:"+json.dumps(value).encode()),[])

    @unittest.skipUnless(Path("native-source/apple-auth/src/client/authentication.cpp").is_file(),"pinned SDK unavailable")
    def test_patch_retains_srp_server_proof_and_explicit_verification_code(self):
        value=patch(Path("native-source/apple-auth/src/client/authentication.cpp").read_bytes())
        self.assertIn('proof.verify(binary(complete, "M2"));',value)
        self.assertIn("integer && in_range && numeric == 0",value)
        self.assertIn('fields["cpd"] = exchange_data;',value)
