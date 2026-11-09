import json
from pathlib import Path
import tempfile
import unittest
from tf_virtual import validate, public_env, pack_private

class VirtualExperimentTests(unittest.TestCase):
    def fixture(self):
        return {"schema":"testflight-virtual-auth-v1","stage":"initialization","status":"failed",
            "virtual_identity":True,"account_login_attempted":False,"gsa_authenticated":False,
            "mac_store_authenticated":False,"tf_authenticated":False,"catalog_received":False,
            "verification_requested":False,"http_status":0,"sdk_error_code":0,
            "apple_error_code":0,"failure_category":"none","last_request_stage":"none","gsa_session_reused":False,"retry_after_known":False,"retry_after_seconds":0}

    def test_raw_account_fields_cannot_be_published(self):
        for key in ("email","headers","sessionId","password","hardware20","error"):
            value=self.fixture();value[key]="PRIVATE"
            with self.assertRaises(ValueError):validate(value)

    def test_catalog_success_requires_all_preceding_proofs(self):
        value=self.fixture();value["status"]="catalog_verified";value["catalog_received"]=True
        with self.assertRaises(ValueError):validate(value)
        for key in ("account_login_attempted","gsa_authenticated","mac_store_authenticated","tf_authenticated"):
            value[key]=True
        self.assertEqual(validate(value)["status"],"catalog_verified")

    def test_boolean_and_status_fields_are_closed(self):
        for key,value in (("virtual_identity",1),("http_status",True),("status","PRIVATE"),("stage","PRIVATE"),("failure_category","PRIVATE"),("apple_error_code",True),("last_request_stage","PRIVATE")):
            candidate=self.fixture();candidate[key]=value
            with self.assertRaises(ValueError):validate(candidate)

    def test_verification_requires_observed_challenge(self):
        value=self.fixture();value["status"]="verification_required"
        with self.assertRaises(ValueError):validate(value)
        value["account_login_attempted"]=True;value["verification_requested"]=True
        self.assertEqual(validate(value)["status"],"verification_required")

    def test_child_does_not_inherit_credentials_or_repository_token(self):
        value=public_env({"HOME":"/synthetic","PATH":"/usr/bin","APPLE_CN_PASSWORD":"PRIVATE","GH_TOKEN":"PRIVATE"})
        self.assertEqual(set(value),{"HOME","PATH","GITHUB_ACTIONS"})
        self.assertNotIn("PRIVATE",json.dumps(value))

    def test_snapshot_rejects_link_and_publicly_readable_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            item=root/"state";item.write_text("SYNTHETIC");item.chmod(0o644)
            with self.assertRaises(ValueError):pack_private(root)
            item.chmod(0o600)
            self.assertGreater(len(pack_private(root)),0)
            (root/"link").symlink_to(item)
            with self.assertRaises(ValueError):pack_private(root)

    def test_restored_gsa_proof_does_not_require_another_password_attempt(self):
        value=self.fixture();value.update(gsa_authenticated=True,gsa_session_reused=True)
        self.assertTrue(validate(value)["gsa_session_reused"])
        value["gsa_session_reused"]=False
        with self.assertRaises(ValueError):validate(value)
