import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
from version_request import selector, resolved_marker, verify_version, VersionError
from telegram_controller import Controller
from telegram_queue import GitHub, QueueError
from delivery_scheduler import matches, app_from_run, version_from_run
from private_export import export, ExportError
from app_preflight import check_app
from capacity import MAX_IPA_BYTES

RID="a"*32
APP="444934666"
OWNER=123456789

def update(text):
    return {"update_id":77,"message":{"date":int(time.time()),"text":text,
        "from":{"id":OWNER,"is_bot":False},"chat":{"id":OWNER,"type":"private"}}}

class HistoricalVersionTests(unittest.TestCase):
    def test_strict_selectors_and_receipt_resolution(self):
        for value in ("9.3.55","842461647","1","1.02.3"):
            self.assertEqual(selector(value),value)
        for value in ("../../secret","1\n2","9.3.55 --output x","１２３","1..2","0"*40,None):
            with self.assertRaises(VersionError):
                selector(value)
        self.assertEqual(resolved_marker("IPA_LAB_VERSION:842461647:9.3.55","9.3.55"),("842461647","9.3.55"))
        for output in ("", "IPA_LAB_VERSION:842461647:9.4.0",
                       "IPA_LAB_VERSION:842461647:9.3.55\nIPA_LAB_VERSION:842461647:9.3.55"):
            with self.assertRaises(VersionError):
                resolved_marker(output,"9.3.55")
        with self.assertRaises(VersionError):
            resolved_marker("IPA_LAB_VERSION:842461648:9.3.55","842461647")
        with self.assertRaises(VersionError):
            verify_version({"version":"9.4.0"},"9.3.55","9.3.55")

    def test_owner_command_dispatch_and_update_deduplication(self):
        bot,gh=Mock(),Mock()
        gh.dispatch.return_value={"status":"queued"}
        c=Controller(bot,gh,OWNER,"crypt","synthetic")
        message=update("/version https://apps.apple.com/cn/app/qq/id444934666 9.3.55")
        c.handle(message)
        c.handle(message)
        gh.preflight_app.assert_called_once_with(APP,historical=True)
        gh.dispatch.assert_called_once_with(APP,c.current["rid"],version="9.3.55")
        self.assertEqual(c.current["version"],"9.3.55")

    def test_bad_command_does_not_dispatch(self):
        for text in ("/version","/version 444934666","/version 444934666 ../x"):
            gh=Mock()
            Controller(Mock(),gh,OWNER,"crypt","synthetic").handle(update(text))
            gh.dispatch.assert_not_called()
            gh.preflight_app.assert_not_called()

    def test_queue_pins_version_in_workflow_input(self):
        gh=GitHub("synthetic")
        gh.find=Mock(return_value=None)
        gh.call=Mock(return_value=None)
        gh.dispatch(APP,RID,version="9.3.55")
        self.assertEqual(gh.call.call_args.args[1]["inputs"]["version"],"9.3.55")

    def test_restart_can_recover_version_from_bound_run(self):
        run={"display_title":"delivery-"+RID+"-app"+APP+"-macos-26-intel-version9.3.55"}
        self.assertTrue(matches(run,RID))
        self.assertEqual(app_from_run(run,RID),APP)
        self.assertEqual(version_from_run(run),"9.3.55")
        self.assertFalse(matches(run,"b"*32))

    def test_latest_size_does_not_reject_smaller_historical_request(self):
        import json
        response=Mock()
        response.__enter__=Mock(return_value=response)
        response.__exit__=Mock(return_value=False)
        response.read.return_value=json.dumps({"resultCount":1,"results":[{
            "trackId":int(APP),"bundleId":"test.app","price":0,"fileSizeBytes":str(MAX_IPA_BYTES+1)}]}).encode()
        opener=Mock()
        opener.open.return_value=response
        with patch("app_preflight.urllib.request.build_opener",return_value=opener):
            self.assertEqual(check_app(APP,historical=True)["trackId"],int(APP))
            with self.assertRaises(ValueError):
                check_app(APP)

    def test_downloaded_wrong_version_stops_before_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            def native(binary,args,env,**kwargs):
                if args[0]=="login":
                    return subprocess.CompletedProcess(args,0,"","")
                if args[0]=="download":
                    self.assertEqual(env["LAB_REQUESTED_VERSION"],"9.3.55")
                    Path(args[args.index("--output")+1]).write_bytes(b"synthetic")
                    return subprocess.CompletedProcess(args,0,"IPA_LAB_VERSION:842461647:9.3.55\n","")
                return subprocess.CompletedProcess(args,0,"","")
            with patch.dict(os.environ,{"GITHUB_ACTIONS":"true","APPLE_ID":"synthetic",
                    "APPLE_PASSWORD":"synthetic","DELIVERY_VERSION":"9.3.55"}), \
                 patch("private_export.readiness",return_value=[]), \
                 patch("private_export.metadata",return_value={"bundleId":"test.app"}), \
                 patch("private_export.check_capacity"), patch("private_export.classify",return_value="authenticated"), \
                 patch("private_export.run",side_effect=native), \
                 patch("private_export.audit",return_value={"bundle_id":"test.app","version":"9.4.0"}), \
                 patch("private_export.subprocess.run") as engine:
                with self.assertRaisesRegex(VersionError,"downloaded_version_mismatch"):
                    export("binary","engine","crypt",APP,RID,"age1"+"a"*58,Path(directory)/"out")
                engine.assert_not_called()

    def test_lookup_failure_does_not_retry_latest(self):
        calls=[]
        def native(binary,args,env,**kwargs):
            calls.append(args[0])
            return subprocess.CompletedProcess(args,2 if args[0]=="download" else 0,
                "IPA_LAB_VERSION_ERROR:version_not_found\n","private account")
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ,{"GITHUB_ACTIONS":"true","APPLE_ID":"synthetic",
                    "APPLE_PASSWORD":"synthetic","DELIVERY_VERSION":"9.3.55"}), \
                 patch("private_export.readiness",return_value=[]), \
                 patch("private_export.metadata",return_value={"bundleId":"test.app"}), \
                 patch("private_export.check_capacity"), patch("private_export.classify",return_value="authenticated"), \
                 patch("private_export.run",side_effect=native):
                with self.assertRaisesRegex(ExportError,"^version_not_found$"):
                    export("binary","engine","crypt",APP,RID,"age1"+"a"*58,Path(directory)/"out")
        self.assertEqual(calls,["login","download","logout"])
