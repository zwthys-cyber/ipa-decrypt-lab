"""Region selection must survive recovery and never cross account boundaries."""
import copy
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from account_profile import parse_target,profile_for_request,workflow_for_request
from telegram_controller import Controller,opaque_id
from telegram_queue import GitHub,QueueError,validate_receipt,request_id
from persistent_journal import PersistentJournal
from task_progress import ProgressCard,WorkerProgress
from app_preflight import check_app,PreflightError
from test_telegram_controller import update,OWNER
import test_app_preflight as fixtures_preflight
import cn_private_export as worker

APP="1530340312"
RID="cn_"+"a"*32
URL="https://apps.apple.com/cn/app/sample/id"+APP

class AccountProfileTests(unittest.TestCase):
    def test_link_country_and_legacy_numeric_default(self):
        for text,profile in ((URL,"cn"),(URL+"?l=en&at=test","cn"),
                (URL.replace("/cn/","/CN/"),"cn"),
                (URL.replace("/cn/","/us/"),"default"),
                (URL.replace("/cn/","/de/"),"default"),(APP,"default"),
                ("https://apps.apple.com/app/id"+APP,"default")):
            self.assertEqual(parse_target(text),(APP,profile))

    def test_untrusted_and_ambiguous_input_rejected(self):
        for text in (URL+" "+APP,URL+"#cn",URL.replace("apps.apple.com","apps.apple.com.evil"),
                     URL.replace("https:","http:"),URL.replace("apps.apple.com","x@apps.apple.com"),
                     URL.replace("apps.apple.com","apps.apple.com:invalid"),URL+"\n",None):
            with self.assertRaises((ValueError,TypeError)):parse_target(text)

    def test_request_profile_namespace_does_not_change_legacy(self):
        self.assertEqual(profile_for_request("c"*32),"default")
        self.assertEqual(workflow_for_request(RID),"china-private-delivery.yml")
        self.assertEqual(request_id(RID),RID)
        for bad in ("cn_"+"a"*31,"CN_"+"a"*32,"cn_cn_"+"a"*32,"c"*33):
            with self.assertRaises((ValueError,QueueError)):request_id(bad)

    def controller(self,journal=None,strict=False):
        bot,gh=Mock(),Mock();gh.dispatch.return_value={"status":"queued"}
        return Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal,strict_ownership=strict),bot,gh

    def test_cn_link_selects_cn_before_dispatch_and_shows_region(self):
        c,bot,gh=self.controller()
        c.handle(update(text=URL))
        rid=c.current["rid"]
        self.assertEqual(rid,"cn_"+opaque_id("synthetic",OWNER,1,APP))
        gh.preflight_app.assert_called_once_with(APP,profile="cn")
        gh.dispatch.assert_called_once_with(APP,rid)
        self.assertIn("中国区",c.card(rid).render("queued"))

    def test_foreign_and_numeric_keep_old_request_identity(self):
        for text in (APP,URL.replace("/cn/","/de/")):
            c,bot,gh=self.controller();c.handle(update(text=text))
            gh.preflight_app.assert_called_once_with(APP)
            gh.dispatch.assert_called_once_with(APP,opaque_id("synthetic",OWNER,1,APP))

    def test_cn_history_keeps_cn_binding_before_query_and_dispatch(self):
        c,bot,gh=self.controller();c.handle(update(text="/version "+URL+" 1.0"))
        gh.preflight_app.assert_called_once_with(APP,historical=True,profile="cn")
        gh.dispatch.assert_called_once_with(APP,c.current["rid"],version="1.0")
        self.assertTrue(c.current["rid"].startswith("cn_"))
        c,bot,gh=self.controller();c.browser.begin=Mock()
        c.handle(update(text="/versions "+URL))
        c.browser.begin.assert_called_once_with(APP,1,profile="cn")

    def test_cn_lookup_failure_never_falls_back_or_records_submission(self):
        c,bot,gh=self.controller();gh.preflight_app.side_effect=PreflightError("app_not_found_in_cn")
        c.handle(update(text=URL))
        gh.dispatch.assert_not_called();self.assertIsNone(c.current)
        self.assertEqual(c.submitted,0)

    def test_queue_dispatch_selects_fixed_cn_workflow_without_foreign_inputs(self):
        gh=GitHub("synthetic");gh.find=Mock(return_value=None);gh.call=Mock(return_value=None)
        gh.dispatch(APP,RID)
        path,payload,method=gh.call.call_args.args
        self.assertEqual(path,"/actions/workflows/china-private-delivery.yml/dispatches")
        self.assertEqual(payload,{"ref":"main","inputs":{"mode":"export","app_id":APP,"request_id":RID}})
        self.assertEqual(method,"POST")
        gh.call.reset_mock()
        gh.dispatch(APP,RID,version="1.0")
        self.assertEqual(gh.call.call_args.args[1]["inputs"]["version"],"1.0")
        gh.call.reset_mock()
        with self.assertRaises(QueueError):gh.retry(APP,RID,123)
        gh.call.assert_not_called()

    def test_run_lookup_rejects_cross_workflow_and_untrusted_branch(self):
        gh=GitHub("synthetic")
        valid={"id":1,"display_title":"delivery-"+RID+"-app"+APP+"-macos-26-intel",
               "event":"workflow_dispatch","head_branch":"main","path":".github/workflows/china-private-delivery.yml"}
        foreign=dict(valid,id=2,path=".github/workflows/private-delivery.yml")
        branch=dict(valid,id=3,head_branch="other")
        gh.call=Mock(return_value={"workflow_runs":[foreign,branch,valid]})
        self.assertEqual(gh.runs(RID),[valid])
        self.assertIn("china-private-delivery.yml/runs",gh.call.call_args.args[0])

    def test_sqlite_restart_and_owner_isolation_keep_cn_binding(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"state.db"
            first=PersistentJournal(path,OWNER);first.write(RID,"pending",APP);first.close()
            journal=PersistentJournal(path,OWNER);other=PersistentJournal(path,OWNER+1)
            try:
                c,bot,gh=self.controller(journal,True)
                gh.find.return_value={"status":"in_progress"}
                c.recover()
                self.assertEqual(c.current["rid"],RID)
                gh.dispatch.assert_not_called()
                self.assertFalse(other.records)
                self.assertFalse(c.failover({"id":123,"status":"queued"}))
                gh.jobs.assert_not_called()
                c.current=None
                c.handle(update(text="/get "+RID))
                gh.deliver.assert_called_once()
            finally:journal.close();other.close()

    def test_receipt_requires_the_same_account_profile(self):
        receipt={"schema":"ipa-private-delivery-v1","status":"encrypted_artifact_ready",
            "request_id":RID,"account_profile":"cn","run_id":"123","source_commit":"f"*40,
            "plaintext_verified":True,"account_data_removed":True,"plaintext_published":False,
            "runtime_verified":False,"app_id":APP,"plaintext_bytes":100,"ciphertext_bytes":200,
            "plaintext_sha256":"b"*64,"ciphertext_sha256":"c"*64}
        validate_receipt(receipt,RID,123,"f"*40)
        for profile in ("default",None):
            bad=dict(receipt);bad.pop("account_profile")
            if profile:bad["account_profile"]=profile
            with self.assertRaises(QueueError):validate_receipt(bad,RID,123,"f"*40)

    def test_cn_metadata_uses_cn_and_requires_cny(self):
        fixtures=fixtures_preflight.AppPreflightTests()
        for currency in ("CNY","USD"):
            context,opener=fixtures.lookup(fixtures.payload(trackId=int(APP),currency=currency))
            with context:
                if currency=="CNY":self.assertEqual(check_app(APP,profile="cn")["currency"],"CNY")
                else:
                    with self.assertRaises(PreflightError):check_app(APP,profile="cn")
            self.assertIn("country=cn",opener.open.call_args.args[0])

    def test_cn_worker_rejects_foreign_secrets_before_loading_session(self):
        with patch.object(worker,"decode") as decoder:
            for key in ("APPLE_ID","APPLE_PASSWORD","APPLE_2FA_CODE","FAIRPLAY_MODEL_B64","FAIRPLAY_STATE_B64"):
                with self.assertRaises(worker.ExportError):worker.validate_profile({key:"synthetic"})
            decoder.assert_not_called()

    def test_cn_session_failure_is_noninteractive_and_cleans_private_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            value={"email":"synthetic@example.invalid","guid":"A"*12,"account":{"store":"143465"}}
            env={"GITHUB_ACTIONS":"true","HOME":directory,"PATH":"/bin"}
            with patch.dict(os.environ,env,clear=True),patch.object(worker,"check_app",return_value={"bundleId":"example.app"}),patch.object(worker,"check_capacity"),patch.object(worker,"validate_profile",return_value=value),patch.object(worker,"run",return_value=Mock(returncode=1)) as native,patch.object(worker,"run_download") as download:
                with self.assertRaisesRegex(worker.ExportError,"cn_session_requires_maintenance"):
                    worker.export("binary","engine","crypt",APP,RID,"age1"+"a"*58,Path(directory)/"out")
                self.assertEqual(native.call_args.args[1],["resume-cn",value["email"],"--guid",value["guid"]])
                self.assertFalse(any("APPLE" in key or "FAIRPLAY" in key for key in native.call_args.args[2]))
                download.assert_not_called()
                self.assertFalse(list((Path(directory)/".ipatool").glob("*/account.json")))

if __name__=="__main__":unittest.main()
