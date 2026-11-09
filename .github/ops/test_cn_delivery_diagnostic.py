import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cn_delivery_diagnostic import summarize

class CNDeliveryDiagnosticTests(unittest.TestCase):
    def test_only_closed_categories_and_numeric_codes_escape(self):
        result=subprocess.CompletedProcess([],1,"IPA_LAB_STAGE:acquire_free_license\nIPA_LAB_FAILURE:9610\nPRIVATE_ACCOUNT\nIPA_LAB_STAGE:PRIVATE_PATH\nIPA_LAB_HTTP:200\n","failureType: 9610 PRIVATE_PASSWORD")
        report=summarize(result)
        self.assertEqual({k:v for k,v in report["diagnostic"].items() if k not in {"store_device_proof_failed","terms_confirmation_required","verification_required","token_expired"}},{"stage":"acquire_free_license","exit_code":1,"apple_failure_code":9610,"http_statuses":[200]})
        self.assertFalse(report["download_succeeded"])
        self.assertNotIn("PRIVATE",json.dumps(report))

    def test_success_remains_download_only_evidence(self):
        report=summarize(subprocess.CompletedProcess([],0,"IPA_LAB_STAGE:publish_file\n",""))
        self.assertTrue(report["download_succeeded"])
        self.assertNotIn("plaintext_verified",report)

class NativeDomainPrivacyTests(unittest.TestCase):
    def test_reviewed_error_domain_only(self):
        report=summarize(subprocess.CompletedProcess([],1,"IPA_LAB_STAGE:acquire_free_license\n","The operation failed. (StoreAMD error 4.) PRIVATE_TOKEN error 12"))
        self.assertEqual(report["native_error_codes"],{"StoreAMD":4})
        self.assertTrue(report["diagnostic"]["store_device_proof_failed"])
        self.assertNotIn("PRIVATE",json.dumps(report))

class HTTPFailurePrivacyTests(unittest.TestCase):
    def test_http_purchase_error_is_classified_without_body(self):
        report=summarize(subprocess.CompletedProcess([],1,"IPA_LAB_STAGE:acquire_free_license\n","Error: request failed with status 302 PRIVATE_ACCOUNT"))
        self.assertEqual(report["transport"]["http_statuses"],[302])
        self.assertEqual(report["error_categories"],["request_failed"])
        self.assertNotIn("PRIVATE",json.dumps(report))

class NativeTracePrivacyTests(unittest.TestCase):
    def test_native_fixed_response_trace(self):
        report=summarize(subprocess.CompletedProcess([],1,"IPA_CN_PURCHASE_HTTP:200\nIPA_CN_PURCHASE_FAILURE:-5000\nIPA_CN_PURCHASE_MESSAGE:true\nIPA_CN_PURCHASE_PHASE:parse_response\nIPA_CN_PURCHASE_ROOT:dictionary\nIPA_CN_PURCHASE_PRIVATE:SECRET\n","PRIVATE_EMAIL"))
        self.assertEqual(report["purchase_trace"],{"http":200,"failure":-5000,"message":True,"phase":"parse_response","root":"dictionary"})
        self.assertNotIn("PRIVATE",json.dumps(report))
