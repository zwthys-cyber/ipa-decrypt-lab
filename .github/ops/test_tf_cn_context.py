import json
import unittest
from unittest.mock import patch
import tf_cn_context

class CookieInspectionTests(unittest.TestCase):
    def inspect(self, cookies):
        with patch.object(tf_cn_context, "decode", return_value=({}, {"cookies": cookies})):
            return tf_cn_context.inspect({}, now=1000)

    def cookie(self, **overrides):
        return dict({"domain": ".apple.com", "path": "/", "name": "synthetic",
                     "value": "FIXTURE_PRIVATE_TOKEN", "expiresAt": 2000}, **overrides)

    def test_only_root_domain_cookie_is_eligible(self):
        for domain, path in [("apple.com", "/"), (".itunes.apple.com", "/"),
                             (".apple.com.evil", "/"), (".apple.com", "/store")]:
            with self.subTest(domain=domain, path=path):
                result = self.inspect([self.cookie(domain=domain, path=path)])
                self.assertEqual(result["unexpired_root_domain_cookie_count"], 0)
                self.assertEqual(result["status"], "mac_store_login_required")

    def test_expired_malformed_and_header_injection_are_excluded(self):
        bad = [self.cookie(expiresAt=999), self.cookie(expiresAt=True),
               self.cookie(expiresAt=float("inf")), self.cookie(value="secret\nraw"),
               self.cookie(name="x=y"), self.cookie(value="raw;leak"), None]
        self.assertEqual(self.inspect(bad)["unexpired_root_domain_cookie_count"], 0)

    def test_closed_report_never_emits_values_or_claims_authentication(self):
        result = self.inspect([self.cookie(), self.cookie(expiresAt=None)])
        self.assertEqual(result["unexpired_root_domain_cookie_count"], 2)
        self.assertNotIn("FIXTURE_PRIVATE_TOKEN", json.dumps(result))
        self.assertEqual(set(result), {"schema", "status", "saved_cn_session_valid",
            "saved_protocol", "cookie_count", "unexpired_root_domain_cookie_count",
            "apple_request_attempted", "invitation_accepted", "credentials_changed",
            "raw_values_published"})
        self.assertFalse(result["apple_request_attempted"])
        self.assertFalse(result["invitation_accepted"])

if __name__ == "__main__":
    unittest.main()
