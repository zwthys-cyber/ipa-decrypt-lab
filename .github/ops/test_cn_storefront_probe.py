import unittest
from cn_storefront_probe import sanitized,BOOLS
class CNStorefrontPrivacy(unittest.TestCase):
    def fixture(self):return dict({k:k not in BOOLS[:3] for k in BOOLS},schema='cn-storefront-contract-v1',status='constructor_observed',default_country='us')
    def test_native_country_override_proof_has_no_hardware_or_account_output(self):
        value=self.fixture();self.assertEqual(sanitized(value),value)
        for k,v in [('guid','PRIVATE'),('token','PRIVATE'),('default_country','PRIVATE'),('authorization_request_attempted',True),('body_preserved',False)]:
            candidate=dict(value);candidate[k]=v
            with self.assertRaises(ValueError):sanitized(candidate)
