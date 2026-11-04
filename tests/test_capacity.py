import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from capacity import MAX_IPA_BYTES, MAX_CIPHER_BYTES, MIN_FREE_BYTES
from private_export import check_capacity, ExportError
from telegram_queue import validate_receipt, QueueError, GitHub
from telegram_controller import Controller

class CapacityTests(unittest.TestCase):
    def test_declared_oversize_and_disk_shortage_rejected(self):
        with patch("private_export.shutil.disk_usage",return_value=Mock(free=MIN_FREE_BYTES)):
            check_capacity({"fileSizeBytes":str(MAX_IPA_BYTES)},Path("."))
            with self.assertRaisesRegex(ExportError,"source_too_large"):
                check_capacity({"fileSizeBytes":str(MAX_IPA_BYTES+1)},Path("."))
        with patch("private_export.shutil.disk_usage",return_value=Mock(free=MIN_FREE_BYTES-1)):
            with self.assertRaisesRegex(ExportError,"insufficient_export_disk"):
                check_capacity({},Path("."))

    def test_receipt_boundary_is_plaintext_not_ciphertext_allowance(self):
        r={"schema":"ipa-private-delivery-v1","status":"encrypted_artifact_ready",
           "request_id":"a"*32,"run_id":"1","source_commit":"b"*40,
           "plaintext_verified":True,"account_data_removed":True,
           "plaintext_published":False,"runtime_verified":False,"app_id":"444934666",
           "plaintext_bytes":MAX_IPA_BYTES,"ciphertext_bytes":MAX_CIPHER_BYTES,
           "plaintext_sha256":"c"*64,"ciphertext_sha256":"d"*64}
        validate_receipt(r,"a"*32,1,"b"*40)
        r["plaintext_bytes"]+=1
        with self.assertRaises(QueueError):
            validate_receipt(r,"a"*32,1,"b"*40)

    def test_fixed_failure_step_becomes_capacity_message(self):
        api=GitHub("synthetic")
        api.jobs=Mock(return_value=[{"steps":[{"name":"IPA exceeds 2000 MB capacity","conclusion":"failure"}]}])
        self.assertIn("2000 MB",api.failure_reason({"id":1}))
        api.jobs.return_value=[{"steps":[{"name":"SECRET UNTRUSTED TEXT","conclusion":"failure"}]}]
        self.assertEqual(api.failure_reason({"id":1}),"")

    def test_controller_reports_capacity_after_workflow_completion(self):
        bot,api=Mock(),Mock()
        controller=Controller(bot,api,123456789,"crypt","synthetic")
        controller.current={"rid":"a"*32,"app":"444934666"}
        api.find.return_value={"id":1,"status":"completed","conclusion":"failure"}
        api.failure_reason.return_value="IPA 超过 2000 MB"
        with patch.object(controller,"failover",return_value=False):
            controller.tick()
        self.assertIn("2000 MB",bot.message.call_args.args[1])
        self.assertIsNone(controller.current)

if __name__=="__main__":
    unittest.main()
