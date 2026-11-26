import copy
import json
import io
from unittest.mock import patch
import unittest
import control_cloud as cloud

class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.source = "a"*40
        self.settings = dict(compatibility_date="2026-07-30", bindings=[
            dict(type="d1",name="DB",id="12345678-1234-1234-1234-123456789abc"),
            dict(type="secret_text",name="PILOT_DRIVE_REFRESH_TOKEN"),
            dict(type="secret_text",name="PILOT_DRIVE_CLIENT_SECRET"),
            dict(type="plain_text",name="PILOT_ENABLED",text="0"),
            dict(type="plain_text",name="PILOT_LINK_ENABLED",text="0")])
        self.origin = "https://ipazake-free-control-pilot.fixture.workers.dev"

    def test_secret_retention_and_existing_database_unchanged(self):
        previous=copy.deepcopy(self.settings)
        metadata=cloud.prepared_metadata(self.settings,self.source,self.origin)
        self.assertEqual(self.settings,previous)
        self.assertEqual(metadata["keep_bindings"],["secret_text"])
        self.assertEqual(next(x for x in metadata["bindings"] if x["name"]=="DB"),self.settings["bindings"][0])
        self.assertFalse(any(x["type"]=="secret_text" for x in metadata["bindings"]))
        self.assertEqual(next(x for x in metadata["bindings"] if x["name"]=="PILOT_ENABLED")["text"],"0")
        self.assertFalse(metadata["observability"]["enabled"])

    def test_active_pilot_cannot_be_overwritten_by_probe(self):
        self.settings["bindings"][-2]["text"]="1"
        with self.assertRaisesRegex(ValueError,"pilot_must_be_disabled"):
            cloud.prepared_metadata(self.settings,self.source,self.origin)

    def test_missing_database_or_invalid_source_refused(self):
        with self.assertRaises(ValueError):
            cloud.prepared_metadata(self.settings,"main",self.origin)
        self.settings["bindings"]=[x for x in self.settings["bindings"] if x["name"]!="DB"]
        with self.assertRaisesRegex(ValueError,"existing_d1_required"):
            cloud.prepared_metadata(self.settings,self.source,self.origin)

    def test_multipart_contains_public_bundle_and_no_preserved_secret_value(self):
        metadata=cloud.prepared_metadata(self.settings,self.source,self.origin)
        body,kind=cloud.multipart(metadata,b"export default {};")
        self.assertIn(b"export default {};",body)
        self.assertIn(b'filename="worker.mjs"',body)
        self.assertIn(b'application/javascript+module',body)
        self.assertIn(b'"keep_bindings": ["secret_text"]',body)
        self.assertTrue(kind.startswith("multipart/form-data; boundary="))

    def test_all_declared_control_operations_use_only_the_fixed_origin(self):
        seen=[]
        class Reply(io.BytesIO):
            def __init__(self):
                super().__init__(b'{"ok":true}')
        class Client:
            def open(self,request,timeout):
                seen.append(request.full_url)
                return Reply()
        with patch.object(cloud.urllib.request,"build_opener",return_value=Client()):
            for path in ("probe-init","probe-submit","probe-status","probe-diagnostics","probe-retire","probe-lease-pending","probe-lease-publish"):
                self.assertTrue(cloud.public_call(self.origin,"synthetic-control-token","/v1/runtime/"+path,{})["ok"])
            with self.assertRaises(ValueError):
                cloud.public_call(self.origin,"synthetic-control-token","/v1/runtime/credentials",{})
        self.assertEqual(len(seen),7)
        self.assertTrue(all(value.startswith(self.origin+"/v1/runtime/") for value in seen))

    def test_admin_token_never_sent_to_arbitrary_origin(self):
        with self.assertRaisesRegex(ValueError,"control_origin_invalid"):
            cloud.public_call("https://evil.invalid","synthetic-control-secret","/v1/runtime/probe-init",{})

if __name__ == "__main__":
    unittest.main()
