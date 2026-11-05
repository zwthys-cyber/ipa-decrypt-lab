import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from app_preflight import check_app, PreflightError, MAX_RESPONSE, main, MESSAGES
from capacity import MAX_IPA_BYTES
from telegram_controller import Controller
from telegram_queue import GitHub
from test_telegram_controller import update, OWNER

APP="510909506"
class AppPreflightTests(unittest.TestCase):
    def payload(self,**fields):
        return {"resultCount":1,"results":[{"trackId":int(APP),"bundleId":"example.app","price":0,
                                          "fileSizeBytes":"1000",**fields}]}
    def lookup(self,payload=None,error=None,raw=None):
        response=Mock()
        response.read.return_value=raw if raw is not None else json.dumps(payload).encode()
        context=Mock()
        context.__enter__=Mock(return_value=response)
        context.__exit__=Mock(return_value=False)
        opener=Mock()
        opener.open.return_value=context
        opener.open.side_effect=error
        return patch("app_preflight.urllib.request.build_opener",return_value=opener),opener

    def test_eligible_uses_fixed_us_query_and_short_timeout(self):
        context,opener=self.lookup(self.payload())
        with context:
            self.assertEqual(check_app(APP)["trackId"],int(APP))
        args,kwargs=opener.open.call_args
        self.assertIn("country=us",args[0])
        self.assertEqual(kwargs["timeout"],8)

    def test_unavailable_paid_and_oversize_are_distinct(self):
        for payload,code in [
            ({"resultCount":0,"results":[]},"app_not_found_in_us"),
            (self.payload(price=1),"paid_app_not_supported"),
            (self.payload(fileSizeBytes=str(MAX_IPA_BYTES+1)),"source_too_large")]:
            context,_=self.lookup(payload)
            with context,self.assertRaises(PreflightError) as caught:
                check_app(APP)
            self.assertEqual(caught.exception.status,code)

    def test_bad_response_is_not_classified_as_unavailable(self):
        for payload in ({},{"results":[]},{"results":[None]},self.payload(trackId=99999),
                        self.payload(price=True),self.payload(fileSizeBytes="bad")):
            context,_=self.lookup(payload)
            with context,self.assertRaises(PreflightError) as caught:
                check_app(APP)
            self.assertEqual(caught.exception.status,"metadata_invalid_response")
        for raw in (b"not-json",b"x"*(MAX_RESPONSE+1)):
            context,_=self.lookup(raw=raw)
            with context,self.assertRaises(PreflightError) as caught:
                check_app(APP)
            self.assertEqual(caught.exception.status,"metadata_invalid_response")

    def test_network_error_is_not_region_error_and_never_echoed(self):
        context,_=self.lookup(error=urllib.error.URLError("private response"))
        with context,self.assertRaises(PreflightError) as caught:
            check_app(APP)
        self.assertEqual(str(caught.exception),"metadata_network_failed")

    def test_invalid_id_never_opens_network(self):
        with patch("app_preflight.urllib.request.build_opener") as opener:
            with self.assertRaises(PreflightError):
                check_app("510909506&country=cn")
            opener.assert_not_called()

    def test_rejected_bot_request_never_records_or_dispatches(self):
        for status in ("app_not_found_in_us","paid_app_not_supported","source_too_large","metadata_network_failed"):
            bot,github,journal=Mock(),Mock(),Mock()
            journal.records={}
            github.preflight_app.side_effect=PreflightError(status)
            controller=Controller(bot,github,OWNER,"crypt","synthetic",journal=journal)
            controller.handle(update(text=APP))
            github.dispatch.assert_not_called()
            journal.write.assert_not_called()
            self.assertIsNone(controller.current)
            self.assertEqual(controller.submitted,0)
            self.assertIn(MESSAGES[status],bot.message.call_args.args[1])

    def test_owner_filter_and_existing_task_precede_public_lookup(self):
        bot,github=Mock(),Mock()
        controller=Controller(bot,github,OWNER,"crypt","synthetic")
        controller.handle(update(uid=OWNER+1,text=APP))
        github.preflight_app.assert_not_called()
        controller.current={"rid":"a"*32,"app":APP}
        controller.handle(update(text=APP,number=2))
        github.preflight_app.assert_not_called()

    def test_success_checks_before_journal_and_dispatch(self):
        bot,github,journal=Mock(),Mock(),Mock()
        journal.records={}
        seen=[]
        github.preflight_app.side_effect=lambda app:seen.append("lookup")
        journal.write.side_effect=lambda *args:seen.append("record")
        github.dispatch.side_effect=lambda *args:(seen.append("dispatch") or {"status":"queued"})
        controller=Controller(bot,github,OWNER,"crypt","synthetic",journal=journal)
        controller.handle(update(text=APP))
        controller.handle(update(text=APP))
        self.assertEqual(seen,["lookup","record","dispatch"])

    def test_worker_failure_reason_can_be_read_without_checks_permission(self):
        github=GitHub("synthetic")
        github.jobs=Mock(return_value=[{"steps":[{"name":"App unavailable in US storefront","conclusion":"failure"}]}])
        self.assertEqual(github.failure_reason({"id":1}),MESSAGES["app_not_found_in_us"])

    def test_workflow_checks_before_external_source_and_apple_secrets(self):
        root=Path(__file__).resolve().parents[1]
        workflow=(root/".github/workflows/private-delivery.yml").read_text()
        acquisition = ("python3 tools/native_runtime.py fetch" if "tools/native_runtime.py fetch" in workflow
                       else "repository: DrWhax/unfairplay")
        self.assertLess(workflow.index("python3 tools/app_preflight.py"), workflow.index(acquisition))
        self.assertLess(workflow.index("python3 tools/app_preflight.py"),
                        workflow.index("secrets.APPLE_PASSWORD"))

if __name__=="__main__":
    unittest.main()
