"""CN history keeps region, account, cursor, receipt and exact version bound."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_controller import Controller
from telegram_queue import QueueError
from version_catalog import CatalogAPI,validate,cache_key
from persistent_journal import PersistentJournal
from version_request import VersionError
import version_catalog_worker as catalog_worker
import cn_private_export as worker
from test_version_catalog import rows,payload,message,OWNER,APP,COMMIT
from test_app_preflight import AppPreflightTests
from app_preflight import check_app,PreflightError
from capacity import MAX_IPA_BYTES
RID="cn_"+"a"*32
URL="https://apps.apple.com/cn/app/id"+APP

class CNHistoryTests(unittest.TestCase):
    def controller(self,journal=None):
        bot,gh=Mock(),Mock()
        bot.call.return_value={"message_id":77,"chat":{"id":OWNER}}
        gh.dispatch.return_value={"status":"queued"}
        return Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal),bot,gh

    def test_cn_and_foreign_catalogs_dispatch_to_distinct_fixed_workflows(self):
        gh=Mock();api=CatalogAPI(gh);api.find=Mock(return_value=None)
        api.dispatch(RID,APP,before="842461648")
        path,body,method=gh.call.call_args.args
        self.assertIn("china-version-catalog.yml",path)
        self.assertNotIn("runner",body["inputs"])
        self.assertEqual(body["inputs"]["before"],"842461648")
        gh.reset_mock();api.dispatch("a"*32,APP)
        self.assertIn("/version-catalog.yml/",gh.call.call_args.args[0])
        self.assertEqual(gh.call.call_args.args[1]["inputs"]["runner"],"macos-26-intel")

    def test_catalog_account_mismatch_rejected_even_with_same_app_and_version(self):
        data=dict(payload(),request_id=RID,account_profile="cn")
        validate(data,RID,APP,1,COMMIT)
        for profile in ("default",None,"tf"):
            wrong=dict(data)
            if profile is None:wrong.pop("account_profile")
            else:wrong["account_profile"]=profile
            with self.assertRaisesRegex(QueueError,"catalog_account_profile_mismatch"):
                validate(wrong,RID,APP,1,COMMIT)

    def test_cn_cache_and_callbacks_keep_region_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            journal=PersistentJournal(Path(folder)/"state.db",OWNER)
            try:
                c,bot,gh=self.controller(journal)
                entry=dict(rows=rows(),total=12,at=int(time.time()))
                c.browser.state["cache"]={APP:dict(entry,rows=[dict(rows()[0],version="99.0")]),cache_key(APP,"cn"):entry}
                c.browser.save()
                c,bot,gh=self.controller(journal)
                c.handle(message(text="/versions "+URL))
                view=c.browser.state["view"]
                self.assertEqual(view["profile"],"cn")
                self.assertNotEqual(view["rows"][0]["version"],"99.0")
                self.assertTrue(view["rid"].startswith("cn_"))
                callback={"update_id":2,"callback_query":{"id":"q","from":{"id":OWNER,"is_bot":False},
                    "message":{"message_id":77,"chat":{"id":OWNER,"type":"private"}},
                    "data":"vc:"+view["rid"]+":v:0"}}
                c.handle(callback)
                self.assertTrue(c.current["rid"].startswith("cn_"))
                gh.preflight_app.assert_called_once_with(APP,historical=True,profile="cn")
                self.assertEqual(gh.dispatch.call_args.kwargs,{"version":rows()[0]["id"]})
            finally:journal.close()

    def test_cn_paging_and_refresh_do_not_drop_account(self):
        c,bot,gh=self.controller()
        c.browser.open(APP,RID,dict(rows=rows(),total=30,at=int(time.time()),next_before="842461600"),"cn")
        c.browser.start=Mock()
        query={"update_id":2,"callback_query":{"id":"q","from":{"id":OWNER,"is_bot":False},
            "message":{"message_id":77,"chat":{"id":OWNER,"type":"private"}},"data":"vc:"+RID+":m:0"}}
        c.handle(query)
        c.browser.start.assert_called_once_with(APP,2,before="842461600",background=False,profile="cn")
        for row in bot.call.call_args_list:
            if row.args[0] in ("sendMessage","editMessageText"):
                for buttons in row.args[1].get("reply_markup",{}).get("inline_keyboard",[]):
                    for button in buttons:self.assertLessEqual(len(button["callback_data"].encode()),64)

    def test_cn_historical_preflight_ignores_latest_size_but_not_currency(self):
        fixture=AppPreflightTests()
        for currency in ("CNY","USD"):
            ctx,opener=fixture.lookup(fixture.payload(trackId=int(APP),currency=currency,fileSizeBytes=str(MAX_IPA_BYTES+1)))
            with ctx:
                if currency=="CNY":check_app(APP,historical=True,profile="cn")
                else:
                    with self.assertRaises(PreflightError):check_app(APP,historical=True,profile="cn")
            self.assertIn("country=cn",opener.open.call_args.args[0])

    def run_export(self,outcome,marker="IPA_LAB_VERSION:842461647:1.0\n"):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        value={"email":"synthetic@example.invalid","guid":"A"*12,"account":{"store":"143465"}}
        env={"GITHUB_ACTIONS":"true","HOME":folder.name,"PATH":"/bin","DELIVERY_VERSION":"1.0","FAIRPLAY_CN_MODEL_B64":"synthetic"}
        def native(binary,args,child,**kwargs):
            if args[0]=="download":
                self.assertEqual(child["LAB_REQUESTED_VERSION"],"1.0")
                self.assertNotIn("APPLEPACKAGE_PASSWORD",child)
                self.assertEqual(args[args.index("--guid")+1],value["guid"])
                if not outcome:Path(args[args.index("--output")+1]).write_bytes(b"fixture")
                return subprocess.CompletedProcess(args,outcome,marker,"private noise")
            return subprocess.CompletedProcess(args,0,"","")
        return folder,value,env,native

    def test_cn_export_passes_exact_resolution_and_only_cn_model(self):
        folder,value,env,native=self.run_export(0)
        with patch.dict(os.environ,env,clear=True),patch.object(worker,"validate_profile",return_value=value),patch.object(worker,"check_app",return_value={"bundleId":"example.app"}) as metadata,patch.object(worker,"check_capacity"),patch.object(worker,"bound_account"),patch.object(worker,"run",side_effect=native),patch.object(worker,"export_original",return_value={}) as export:
            worker.export("binary","engine","crypt",APP,RID,"age1"+"a"*58,Path(folder.name)/"out")
            metadata.assert_called_once_with(APP,historical=True,profile="cn")
            self.assertEqual(export.call_args.args[-3:],("1.0","842461647","1.0"))
            self.assertEqual(export.call_args.kwargs,{"profile":"cn"})
            self.assertNotIn("FAIRPLAY_MODEL_B64",os.environ)
        self.assertFalse(list(Path(folder.name).glob(".ipatool/*/account.json")))

    def test_failed_or_wrong_resolution_never_falls_back_latest_or_calls_engine(self):
        for code,marker,error in ((2,"IPA_LAB_VERSION_ERROR:version_not_found\n",worker.ExportError),
                (0,"IPA_LAB_VERSION:842461647:2.0\n",VersionError),(0,"",VersionError)):
            folder,value,env,native=self.run_export(code,marker)
            with patch.dict(os.environ,env,clear=True),patch.object(worker,"validate_profile",return_value=value),patch.object(worker,"check_app",return_value={"bundleId":"example.app"}),patch.object(worker,"check_capacity"),patch.object(worker,"bound_account"),patch.object(worker,"run",side_effect=native) as commands,patch.object(worker,"export_original") as export:
                with self.assertRaises(error):worker.export("binary","engine","crypt",APP,RID,"age1"+"a"*58,Path(folder.name)/"out")
                export.assert_not_called()
                self.assertEqual([x.args[1][0] for x in commands.call_args_list],["resume-cn","download"])

    def test_catalog_worker_cn_is_metadata_only_and_never_mounts_foreign_password(self):
        with tempfile.TemporaryDirectory() as folder:
            env={"GITHUB_ACTIONS":"true","CATALOG_ACCOUNT_PROFILE":"cn","CATALOG_REQUEST_ID":RID,"CATALOG_APP_ID":APP,"CATALOG_PAGED":"1","GITHUB_RUN_ID":"1","GITHUB_SHA":COMMIT}
            @contextlib.contextmanager
            def session(binary,profile,environment):
                self.assertEqual(profile,"cn")
                yield "synthetic@example.invalid",{},["--guid","A"*12]
            native=subprocess.CompletedProcess([],0,"IPA_LAB_CATALOG_TOTAL:1\nIPA_LAB_CATALOG_ITEM:842461647:1.0:2026-01-01\nIPA_LAB_CATALOG_NEXT:end\n","private noise")
            old=os.getcwd()
            try:
                os.chdir(folder)
                with patch.dict(os.environ,env,clear=True),patch.object(sys,"argv",["worker","binary"]),patch.object(catalog_worker,"catalog_session",side_effect=session),patch.object(catalog_worker,"check_app",return_value={"bundleId":"example.app","version":"2.0"}),patch.object(catalog_worker,"run",return_value=native) as run,contextlib.redirect_stdout(io.StringIO()) as logs:
                    self.assertEqual(catalog_worker.main(),0)
                    child=run.call_args.args[2]
                    self.assertEqual(child["LAB_VERSION_CATALOG"],"1")
                    self.assertNotIn("APPLEPACKAGE_PASSWORD",child)
                    self.assertNotIn("private noise",logs.getvalue())
                    result=json.loads(Path("catalog-out/versions.json").read_text())
                    self.assertEqual(result["account_profile"],"cn")
                    self.assertEqual(result["current_version"],"2.0")
            finally:os.chdir(old)

class CNHistoryProofTests(unittest.TestCase):
    def test_real_sample_selector_requires_strictly_older_cn_metadata(self):
        import importlib.util
        path=Path(__file__).resolve().parents[1]/".github/ops/cn_history_proof.py"
        spec=importlib.util.spec_from_file_location("cn_history_proof_fixture",path)
        proof=importlib.util.module_from_spec(spec);spec.loader.exec_module(proof)
        data=dict(payload(),request_id=proof.CATALOG_RID,app_id=proof.APP,account_profile="cn",
                  current_version="10.0",rows=[dict(rows()[0],version="9.0")],total=1)
        self.assertEqual(proof.choose(data,1,COMMIT)["version"],"9.0")
        for version in ("10.0","11.0"):
            wrong=dict(data,rows=[dict(data["rows"][0],version=version)])
            with self.assertRaises(AssertionError):proof.choose(wrong,1,COMMIT)
        with self.assertRaises(QueueError):proof.choose(dict(data,account_profile="default"),1,COMMIT)

if __name__=="__main__":unittest.main()

