import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_queue import GitHub,QueueError
from telegram_controller import Controller
from persistent_journal import PersistentJournal
from telegram_api import APIError

RID="a"*32
OWNER=123456789

class DeliveryResilienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def response(self):
        response=MagicMock()
        response.__enter__.return_value=response
        response.read.side_effect=[b"synthetic-ciphertext",b""]
        return response

    def test_initial_get_timeout_retried_without_leaking_exception(self):
        api=GitHub("synthetic")
        api.opener=Mock()
        api.opener.open.side_effect=[urllib.error.URLError("private signed URL"),self.response()]
        path=self.root/"archive.zip"
        api.archive(1,path)
        self.assertEqual(path.read_bytes(),b"synthetic-ciphertext")
        self.assertEqual(api.opener.open.call_count,2)

    def test_repeated_transport_failure_is_sanitized(self):
        api=GitHub("synthetic")
        api.opener=Mock()
        api.opener.open.side_effect=urllib.error.URLError("PRIVATE_TOKEN")
        with self.assertRaisesRegex(QueueError,"^artifact_transport_failed$"):
            api.archive(1,self.root/"archive.zip")
        self.assertEqual(api.opener.open.call_count,2)

    def test_existing_destination_never_deleted(self):
        path=self.root/"archive.zip"
        path.write_bytes(b"keep")
        api=GitHub("synthetic")
        api.opener=Mock()
        with self.assertRaisesRegex(QueueError,"artifact_destination_exists"):
            api.archive(1,path)
        self.assertEqual(path.read_bytes(),b"keep")
        api.opener.open.assert_not_called()

    def controller(self):
        journal=PersistentJournal(self.root/"state.sqlite3",OWNER)
        self.addCleanup(journal.close)
        bot,api=Mock(),Mock()
        controller=Controller(bot,api,OWNER,"crypt","synthetic",journal=journal)
        return controller,bot,api,journal

    def test_unexpected_fetch_failure_stays_local_and_not_sending(self):
        controller,bot,api,journal=self.controller()
        api.deliver.side_effect=ValueError("PRIVATE_URL")
        self.assertFalse(controller.deliver(RID))
        self.assertEqual(journal.records[RID]["state"],"closed")
        text=" ".join(str(call.args) for call in bot.message.call_args_list)
        self.assertIn("尚未开始",text)
        self.assertNotIn("PRIVATE_URL",text)
        self.assertNotIn("结果未确认",text)

    def test_send_intent_is_recorded_only_at_upload(self):
        controller,bot,api,journal=self.controller()
        def send(*args,**kwargs):
            self.assertEqual(journal.records[RID]["state"],"pending")
            kwargs["progress"]("delivery_verifying")
            self.assertEqual(journal.records[RID]["state"],"pending")
            kwargs["progress"]("uploading")
            self.assertEqual(journal.records[RID]["state"],"sending")
            raise APIError("telegram_transport_unknown")
        api.deliver.side_effect=send
        self.assertFalse(controller.deliver(RID))
        self.assertEqual(journal.records[RID]["state"],"sending")
        controller.recover()
        self.assertEqual(api.deliver.call_count,1)

    def test_unexpected_exception_after_upload_is_not_repeated(self):
        controller,bot,api,journal=self.controller()
        def send(*args,**kwargs):
            kwargs["progress"]("uploading")
            raise RuntimeError("PRIVATE_RESPONSE")
        api.deliver.side_effect=send
        self.assertFalse(controller.deliver(RID))
        self.assertEqual(journal.records[RID]["state"],"sending")
        controller.recover()
        self.assertEqual(api.deliver.call_count,1)

if __name__=="__main__":
    unittest.main()
