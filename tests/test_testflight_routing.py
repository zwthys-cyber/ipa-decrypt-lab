"""TF routing must never substitute App Store, leak tenants, or repeat acceptance."""
import base64
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from account_profile import parse_target,profile_for_request,workflow_for_request
from telegram_controller import Controller
from telegram_queue import GitHub,QueueError
from persistent_journal import PersistentJournal
from delivery_scheduler import matches,app_from_run
import testflight_state as state
from test_telegram_controller import update,OWNER

INVITE="SYNTH123"
RID="tf_"+"a"*32
class TestFlightRouting(unittest.TestCase):
    def test_strict_links_and_independent_request_namespace(self):
        self.assertEqual(parse_target("https://testflight.apple.com/join/"+INVITE),(INVITE,"tf"))
        self.assertEqual(parse_target("itms-beta://testflight.apple.com/join/"+INVITE),(INVITE,"tf"))
        self.assertEqual(profile_for_request(RID),"tf")
        self.assertEqual(workflow_for_request(RID),"testflight-private-delivery.yml")
        for bad in ("https://testflight.apple.com.evil/join/"+INVITE,
                "https://user@testflight.apple.com/join/"+INVITE,"http://testflight.apple.com/join/"+INVITE,
                "https://testflight.apple.com/join/"+INVITE+"?next=https://evil.invalid",
                "https://testflight.apple.com/join/../../OTHER","https://testflight.apple.com/join/"+INVITE+"#x"):
            with self.assertRaises(ValueError):parse_target(bad)
    def test_only_enabled_owner_route_dispatches_without_store_preflight(self):
        for enabled in (False,True):
            bot,gh=Mock(),Mock();gh.dispatch.return_value={"status":"queued"}
            c=Controller(bot,gh,OWNER,"crypt","synthetic");c.testflight_allowed=enabled
            c.handle(update(text="https://testflight.apple.com/join/"+INVITE))
            gh.preflight_app.assert_not_called()
            if enabled:
                self.assertTrue(c.current["rid"].startswith("tf_"));gh.dispatch.assert_called_once_with(INVITE,c.current["rid"])
            else:gh.dispatch.assert_not_called()
    def test_history_is_rejected_without_dispatch(self):
        for text in ("/versions https://testflight.apple.com/join/"+INVITE,
                "/version https://testflight.apple.com/join/"+INVITE+" 1.2"):
            bot,gh=Mock(),Mock();c=Controller(bot,gh,OWNER,"crypt","synthetic");c.testflight_allowed=True
            c.handle(update(text=text));gh.dispatch.assert_not_called();gh.preflight_app.assert_not_called()
    def test_queue_uses_fixed_tf_workflow_and_no_automatic_retry(self):
        gh=GitHub("synthetic");gh.find=Mock(return_value=None);gh.call=Mock(return_value=None)
        gh.dispatch(INVITE,RID)
        self.assertEqual(gh.call.call_args.args,("/actions/workflows/testflight-private-delivery.yml/dispatches",
            {"ref":"main","inputs":{"mode":"export","invite":INVITE,"request_id":RID}},"POST"))
        gh.call.reset_mock()
        for invoke in (lambda:gh.dispatch(INVITE,RID,version="1.0"),lambda:gh.retry(INVITE,RID,1)):
            with self.assertRaises(QueueError):invoke()
        gh.call.assert_not_called()
    def test_restart_preserves_target_and_rejects_appstore_title(self):
        title="delivery-"+RID+"-tf"+INVITE+"-macos-26-intel"
        self.assertTrue(matches({"display_title":title},RID))
        self.assertEqual(app_from_run({"display_title":title},RID),INVITE)
        self.assertFalse(matches({"display_title":"delivery-"+RID+"-app123456-macos-26-intel"},RID))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"state";ledger=PersistentJournal(path,OWNER);ledger.write(RID,"pending",INVITE);ledger.close()
            ledger=PersistentJournal(path,OWNER);other=PersistentJournal(path,OWNER+1)
            self.assertEqual(ledger.records[RID]["app"],INVITE);self.assertFalse(other.records)
            ledger.close();other.close()

class TestFlightDurability(unittest.TestCase):
    def request(self,**kwargs):
        return dict(invite=INVITE,request_id=RID,run_id="123",source_commit="b"*40,**kwargs)
    def test_intent_survives_restart_expiry_and_another_request(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700);db=state.connect(root);permit=state.claim(db,self.request(),now=1)
            self.assertTrue(permit["permitted"]);db.close();db=state.connect(root)
            value=self.request();value.update(request_id="tf_"+"c"*32,run_id="456")
            self.assertFalse(state.claim(db,value,now=10000)["permitted"])
            self.assertFalse(state.claim(db,dict(value,invite="yoNuHexZ"))["permitted"]);db.close()
    def test_forged_finish_cannot_replace_another_intent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700);db=state.connect(root);permit=state.claim(db,self.request())
            value=dict(self.request(),nonce="0"*32,outcome="membership_verified")
            with self.assertRaises(ValueError):state.finish(db,value)
            value["nonce"]=permit["nonce"];self.assertTrue(state.finish(db,value)["recorded"])
            self.assertFalse(state.claim(db,self.request())["permitted"]);db.close()
    def test_ciphertext_is_immutable_and_plaintext_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);root.chmod(0o700);raw=b"age-encryption.org/v1\nSYNTHETIC_CIPHERTEXT"
            value=dict(schema="tf-durable-state-v1",origin_run=state.ORIGIN,ciphertext_b64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
            first=state.install_cipher(root,value);self.assertEqual(state.install_cipher(root,value),first)
            changed=raw+b"DIFFERENT";value.update(ciphertext_b64=base64.b64encode(changed).decode(),sha256=hashlib.sha256(changed).hexdigest())
            with self.assertRaises(ValueError):state.install_cipher(root,value)
            self.assertEqual(state.status(root)["sha256"],first["sha256"])
            value.update(ciphertext_b64=base64.b64encode(b"PLAINTEXT_PRIVATE").decode(),sha256=hashlib.sha256(b"PLAINTEXT_PRIVATE").hexdigest())
            with self.assertRaises(ValueError):state.install_cipher(root,value)
