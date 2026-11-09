import json
import unittest
from cn_platform_preflight import summary
class CNPublicPlatformBoundaries(unittest.TestCase):
    def test_public_summary_never_asserts_decryption_or_exposes_private_inputs(self):
        report=summary('macos-15','arm64','24G123',False,True)
        for k in ('credentials_loaded','authorization_request_attempted','deauthorization_attempted','model_recovered','platform_decryption_proven'):self.assertIs(report[k],False)
        self.assertNotIn('hardware',json.dumps(report));self.assertNotIn('guid',json.dumps(report));self.assertEqual(len(report),11)
    def test_unknown_or_mismatched_platform_cannot_claim_readiness(self):
        for args in [('self-hosted','arm64','24G123',False,True),('macos-15','x86_64','24G123',False,True),('macos-26-intel','x86_64','PRIVATE/PATH',False,True),('macos-15','arm64','24G123',0,True)]:
            with self.assertRaises(ValueError):summary(*args)
