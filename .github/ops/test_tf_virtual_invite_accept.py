import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from tf_virtual_invite_accept import runtime,validate_packet,payload_valid,membership,target,Stop
class AcceptIntentTests(unittest.TestCase):
    def env(self):
        return dict(GITHUB_ACTIONS="true",GITHUB_REF="refs/heads/main",GITHUB_RUN_ATTEMPT="1",
            GITHUB_RUN_ID="12345",GITHUB_SHA="a"*40)
    def packet(self):
        cipher=b"age-encryption.org/v1\nSYNTHETIC"
        return dict(schema="tf-invite-intent-packet-v1",worker_run="12345",source_commit="a"*40,
            nonce="b"*32,expires=1300,account_binding="c"*64,
            record_path=".github/ops/tf_invite_intents/"+("c"*64)+".json",
            ciphertext_b64=base64.b64encode(cipher).decode(),cipher_sha256=hashlib.sha256(cipher).hexdigest())
    def test_attempt_two_and_foreign_branch_cannot_execute(self):
        runtime(self.env())
        for key,value in (("GITHUB_RUN_ATTEMPT","2"),("GITHUB_REF","refs/heads/foreign"),("GITHUB_ACTIONS","false")):
            env=self.env();env[key]=value
            with self.assertRaises(Stop):runtime(env)
    def test_packet_binds_worker_source_expiry_and_exact_path(self):
        self.assertEqual(validate_packet(self.packet(),self.env(),1000)["worker_run"],"12345")
        for key,value in (("worker_run","99999"),("source_commit","d"*40),("expires",1000),
            ("expires",1700),("expires",True),("record_path","../PRIVATE"),("cipher_sha256","0"*64)):
            item=self.packet();item[key]=value
            with self.assertRaises((Stop,ValueError)):validate_packet(item,self.env(),1000)
        item=self.packet();item["sessionId"]="PRIVATE"
        with self.assertRaises(Stop):validate_packet(item,self.env(),1000)
    def test_payload_cannot_change_account_app_or_origin(self):
        packet=self.packet();profile=dict(run_id="777",source_commit="e"*40)
        payload=dict(schema="tf-invite-intent-v1",worker_run="12345",source_commit="a"*40,nonce="b"*32,
            issued_at=1000,expires=1300,account_binding="c"*64,app_binding="f"*64,invite="yoNuHexZ",
            origin_run="777",origin_source="e"*40)
        payload_valid(payload,packet,"f"*64,profile,1001)
        for key,value in (("app_binding","0"*64),("invite","different"),("nonce","0"*32),
                          ("origin_run","888"),("account_binding","0"*64),("issued_at",2000)):
            item=copy.deepcopy(payload);item[key]=value
            with self.assertRaises(Stop):payload_valid(item,packet,"f"*64,profile,1001)
    def test_membership_requires_bundle_and_app_id(self):
        good=dict(bundleId="example.fixture",appAdamId="123")
        self.assertTrue(membership([good,copy.deepcopy(good)],"example.fixture","123"))
        self.assertFalse(membership([dict(name="A.I.",bundleId="example.other",appAdamId="123")],"example.fixture","123"))
        self.assertFalse(membership([dict(bundleId="example.fixture",appAdamId="456")],"example.fixture","123"))
    def test_additional_agreement_is_never_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);value=dict(status="OPEN",app=dict(name="A.I.",bundleId="example.fixture",appAdamId="123"))
            (root/"invitation.json").write_text(json.dumps(value));target(root)
            value["requiresAgreement"]=True;(root/"invitation.json").write_text(json.dumps(value))
            with self.assertRaises(Stop):target(root)
