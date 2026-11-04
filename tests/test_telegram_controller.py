import copy
import hashlib
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_api import APIError
from telegram_queue import QueueError, validate_receipt, request_id
from telegram_controller import Controller, opaque_id, owner_id, target_id

OWNER=123456789
RID="a"*32

def update(uid=OWNER,text="6599842047",number=1):
    return {"update_id":number,"message":{"date":int(time.time()),"text":text,
        "from":{"id":uid,"is_bot":False},"chat":{"id":uid,"type":"private"}}}

class ControllerTests(unittest.TestCase):
    def controller(self):
        bot,gh=Mock(),Mock()
        gh.dispatch.return_value={"status":"queued"}
        return Controller(bot,gh,OWNER,"/private/crypt","synthetic-token"),bot,gh

    def test_resume_keeps_running_job_without_resubmitting(self):
        c,bot,gh=self.controller()
        gh.find.return_value={"status":"in_progress"}
        c.resume(RID)
        self.assertEqual(c.current["rid"],RID)
        gh.dispatch.assert_not_called()
        gh.deliver.assert_not_called()

    def test_only_owner_private_messages_submit(self):
        c,bot,gh=self.controller()
        c.handle(update(55))
        u=update();u["message"]["chat"]["type"]="group";c.handle(u)
        old=update();old["message"]["date"]-=1000;c.handle(old)
        gh.dispatch.assert_not_called()
        bot.message.assert_not_called()

    def test_first_submission_is_allowed_on_a_fresh_runner(self):
        c,bot,gh=self.controller()
        with patch("telegram_controller.time.monotonic",return_value=1):
            c.handle(update())
        gh.dispatch.assert_called_once()

    def test_duplicate_update_dispatches_once(self):
        c,bot,gh=self.controller()
        c.handle(update())
        c.handle(update())
        gh.dispatch.assert_called_once()
        self.assertEqual(gh.dispatch.call_args.args[0],"6599842047")
        self.assertRegex(gh.dispatch.call_args.args[1],r"^[a-f0-9]{32}$")

    def test_ambiguous_dispatch_preserves_job_and_does_not_retry(self):
        c,bot,gh=self.controller()
        gh.dispatch.side_effect=QueueError("github_transport_unknown")
        c.handle(update())
        c.handle(update(number=2))
        gh.dispatch.assert_called_once()
        self.assertIsNotNone(c.current)

    def test_cancel_only_current_job(self):
        c,bot,gh=self.controller()
        c.handle(update(text="/cancel"))
        gh.cancel.assert_not_called()
        c.handle(update(number=2))
        c.handle(update(text="/cancel",number=3))
        gh.cancel.assert_called_once_with(opaque_id("synthetic-token",OWNER,2,"6599842047"))
        self.assertIsNone(c.current)

    def test_unknown_send_is_not_automatically_retried(self):
        c,bot,gh=self.controller()
        c.current={"rid":RID,"app":"6599842047","state":"in_progress","since":time.monotonic()}
        gh.find.return_value={"status":"completed","conclusion":"success"}
        gh.deliver.side_effect=APIError("telegram_transport_unknown")
        c.tick();c.tick()
        gh.deliver.assert_called_once()
        self.assertIsNone(c.current)

    def test_manual_get_does_not_trigger_duplicate_automatic_send(self):
        c,bot,gh=self.controller()
        c.current={"rid":RID,"app":"6599842047","state":"in_progress","since":time.monotonic()}
        gh.find.return_value={"status":"completed","conclusion":"success"}
        gh.deliver.return_value={"status":"telegram_file_delivered","request_id":RID,"bytes":100}
        c.handle(update(text="/get "+RID))
        c.tick()
        gh.deliver.assert_called_once()
        self.assertIsNone(c.current)

    def test_strict_target(self):
        self.assertEqual(target_id("https://apps.apple.com/us/app/name/id6599842047?l=en"),"6599842047")
        for bad in ("https://example.com/id6599842047","https://apps.apple.com.evil/id6599842047",
            "https://user:pass@apps.apple.com/us/id6599842047",
            "http://apps.apple.com/id6599842047","https://apps.apple.com:8080/id6599842047",
            "https://apps.apple.com/id6599842047#fragment","6599842047; echo secret",
            "https://apps.apple.com/id6599842047\n"):
            with self.assertRaises(ValueError,msg=bad):
                target_id(bad)
        with self.assertRaises(APIError):
            owner_id("username")

    def test_receipt_must_match_run_commit_and_full_verification(self):
        receipt={"schema":"ipa-private-delivery-v1","status":"encrypted_artifact_ready",
            "request_id":RID,"run_id":"123","source_commit":"f"*40,"plaintext_verified":True,
            "account_data_removed":True,"plaintext_published":False,"runtime_verified":False,
            "app_id":"6599842047","plaintext_bytes":100,"ciphertext_bytes":200,
            "plaintext_sha256":"b"*64,"ciphertext_sha256":"c"*64}
        validate_receipt(receipt,RID,123,"f"*40)
        for key,value in (("source_commit","other"),("run_id","999"),("request_id","other"),
            ("plaintext_verified",False),("account_data_removed",False),("plaintext_published",True),
            ("plaintext_bytes",True),("ciphertext_sha256","bad")):
            bad=copy.deepcopy(receipt);bad[key]=value
            with self.assertRaises(QueueError,msg=key):
                validate_receipt(bad,RID,123,"f"*40)

if __name__=="__main__":
    unittest.main()
