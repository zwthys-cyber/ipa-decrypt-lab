import copy
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from version_catalog import validate, CatalogAPI, VersionBrowser
from version_catalog_worker import parse_rows
from telegram_controller import Controller
from persistent_journal import PersistentJournal
from telegram_daemon import process_update
from telegram_queue import QueueError

OWNER=123456789
APP="444934666"
RID="a"*32
COMMIT="b"*40

def rows(count=12):
    return [{"id":str(842461647+i),"version":"9.3."+str(i),"date":"2026-10-01"} for i in range(count)]

def payload():
    return dict(schema="ipa-version-catalog-v1",request_id=RID,app_id=APP,
                run_id="1",source_commit=COMMIT,total=12,rows=rows())

def message(number=1,text="/versions "+APP):
    return {"update_id":number,"message":{"date":int(time.time()),"from":{"id":OWNER,"is_bot":False},
        "chat":{"id":OWNER,"type":"private"},"text":text}}

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.journal=PersistentJournal(Path(self.temp.name)/"state.sqlite3",OWNER)
        self.addCleanup(self.journal.close)
        self.bot=Mock()
        self.bot.call.return_value={"message_id":77,"chat":{"id":OWNER}}
        self.gh=Mock()
        self.gh.dispatch.return_value={"status":"queued"}
        self.c=Controller(self.bot,self.gh,OWNER,"crypt","synthetic",journal=self.journal)
        self.c.browser.open(APP,RID,dict(rows=rows(),total=20,at=int(time.time())))

    def callback(self,number=2,action="v",index=0):
        return {"update_id":number,"callback_query":{"id":"query-"+str(number),
            "from":{"id":OWNER,"is_bot":False},"message":{"message_id":77,"chat":{"id":OWNER,"type":"private"}},
            "data":"vc:"+RID+":"+action+":"+str(index)}}

    def test_bound_metadata_and_size_validation(self):
        self.assertEqual(len(validate(payload(),RID,APP,1,COMMIT)["rows"]),12)
        for key,value in (("app_id","12345"),("request_id","c"*32),("run_id","2"),("source_commit","c"*40),
                          ("total",True),("rows",rows(61))):
            bad=payload();bad[key]=value
            with self.assertRaises(QueueError):
                validate(bad,RID,APP,1,COMMIT)
        bad=payload();bad["rows"][0]["url"]="private"
        with self.assertRaises(QueueError):
            validate(bad,RID,APP,1,COMMIT)

    def test_native_output_filters_private_noise(self):
        total,result=parse_rows("private account noise\nIPA_LAB_CATALOG_TOTAL:2\nIPA_LAB_CATALOG_ITEM:842461647:9.3.55:2026-10-01\n")
        self.assertEqual(total,2)
        self.assertEqual(result,[dict(id="842461647",version="9.3.55",date="2026-10-01")])
        for output in ("private response","IPA_LAB_CATALOG_TOTAL:0\n",
                       "IPA_LAB_CATALOG_TOTAL:1\nIPA_LAB_CATALOG_ITEM:../bad:9.3.55:2026-10-01"):
            with self.assertRaises(ValueError):
                parse_rows(output)

    def test_pagination_does_not_query_or_download(self):
        self.bot.call.reset_mock()
        self.c.handle(self.callback(action="p",index=1))
        self.gh.dispatch.assert_not_called()
        self.gh.call.assert_not_called()
        calls=[call for call in self.bot.call.call_args_list if call.args[0]=="editMessageText"]
        self.assertEqual(len(calls),1)
        body=calls[0].args[1]
        self.assertIn("第 2/2 页",body["text"])
        for row in body["reply_markup"]["inline_keyboard"]:
            for button in row:
                self.assertLessEqual(len(button["callback_data"].encode()),64)

    def test_selection_pins_external_id_and_is_one_use_after_restart(self):
        process_update(self.c,self.journal,self.callback())
        self.gh.dispatch.assert_called_once()
        self.assertEqual(self.gh.dispatch.call_args.kwargs,{"version":"842461647"})
        self.assertEqual(self.journal.daily_submissions(),1)
        second=Controller(self.bot,self.gh,OWNER,"crypt","synthetic",journal=self.journal)
        process_update(second,self.journal,self.callback(number=3))
        self.gh.dispatch.assert_called_once()
        self.assertEqual(second.browser.state["view"]["used"],[0])

    def test_foreign_owner_chat_message_and_expired_buttons_rejected(self):
        original=self.callback()
        variants=[]
        for key,value in (("id",12345),("is_bot",True)):
            bad=copy.deepcopy(original);bad["callback_query"]["from"][key]=value;variants.append(bad)
        bad=copy.deepcopy(original);bad["callback_query"]["message"]["chat"]["type"]="group";variants.append(bad)
        bad=copy.deepcopy(original);bad["callback_query"]["message"]["message_id"]=99;variants.append(bad)
        bad=copy.deepcopy(original);bad["callback_query"]["data"]="vc:"+"c"*32+":v:0";variants.append(bad)
        for bad in variants:
            self.c.handle(bad)
        self.c.browser.state["view"]["at"]=int(time.time())-21601
        self.c.handle(original)
        self.gh.dispatch.assert_not_called()

    def test_quota_and_active_task_still_block_selection(self):
        self.c.submitted=self.c.submission_limit
        self.c.handle(self.callback())
        self.gh.dispatch.assert_not_called()
        self.assertEqual(self.c.browser.state["view"]["used"],[])
        self.c.current={"rid":"c"*32}
        self.c.handle(self.callback(number=3))
        self.gh.dispatch.assert_not_called()

    def test_pending_query_survives_restart_without_second_post(self):
        self.c.browser.api=Mock()
        self.c.browser.begin(APP,10)
        self.c.browser.api.dispatch.assert_called_once()
        second=Controller(self.bot,self.gh,OWNER,"crypt","synthetic",journal=self.journal)
        second.browser.api=Mock()
        second.browser.api.find.return_value=None
        second.browser.tick()
        second.browser.api.dispatch.assert_not_called()
        self.assertIsNotNone(second.browser.state["pending"])

    def test_cache_reopens_without_github_dispatch(self):
        self.c.browser.state["cache"]={APP:dict(rows=rows(),total=12,at=int(time.time()))}
        self.c.browser.api=Mock()
        self.c.handle(message())
        self.c.browser.api.dispatch.assert_not_called()
        self.assertNotEqual(self.c.browser.state["view"]["rid"],RID)

    def test_completed_catalog_is_saved_and_rendered(self):
        self.c.browser.state["pending"]={"rid":RID,"app":APP,"at":int(time.time())}
        self.c.browser.api=Mock()
        self.c.browser.api.find.return_value={"status":"completed","conclusion":"success"}
        self.c.browser.api.result.return_value={"rows":rows(),"total":12}
        self.c.browser.tick()
        self.assertIsNone(self.c.browser.state["pending"])
        saved=self.journal.browser_load()
        self.assertEqual(saved["view"]["message_id"],77)
        self.assertEqual(len(saved["cache"][APP]["rows"]),12)

    def test_unavailable_result_stops_after_bounded_attempts(self):
        self.c.browser.state["pending"]={"rid":RID,"app":APP,"at":int(time.time())}
        self.c.browser.api=Mock()
        self.c.browser.api.find.return_value={"status":"completed","conclusion":"success"}
        self.c.browser.api.result.side_effect=QueueError("catalog_artifact_unavailable")
        for attempt in range(3):
            self.c.browser.last_poll=0
            self.c.browser.tick()
        self.assertIsNone(self.journal.browser_load()["pending"])

    def test_ambiguous_catalog_dispatch_is_not_repeated(self):
        self.c.browser.api=Mock()
        self.c.browser.api.dispatch.side_effect=QueueError("github_transport_unknown")
        self.c.browser.begin(APP,10)
        self.c.browser.begin(APP,11)
        self.c.browser.api.dispatch.assert_called_once()
        self.assertIsNotNone(self.journal.browser_load()["pending"])
