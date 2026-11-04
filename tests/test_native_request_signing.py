import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_request_signing as mod

class SigningReportContracts(unittest.TestCase):
    def ready(self):
        return dict(status="signature_ready", endpoint_supported=True, policy_checked=True,
            signing_attempted=True, body_unchanged=True, destination_unchanged=True,
            other_headers_unchanged=True, error_present=False, signature_present=True, signature_valid=True)

    def test_private_fields_never_publish_or_create_enrollment_claims(self):
        value = self.ready()
        value.update(signature="SECRET", headers={"Cookie": "SECRET"}, body="SECRET",
                     enrollment_created=True, decryption_proven=True, account_login_attempted=True)
        result = mod.clean(value)
        self.assertNotIn("SECRET", json.dumps(result))
        for field in ("enrollment_created", "decryption_proven", "account_login_attempted", "authorization_request_attempted"):
            self.assertFalse(result[field])

    def test_signature_requires_intact_request_and_valid_signature(self):
        good = self.ready()
        self.assertEqual(mod.clean(good)["status"], "signature_ready")
        for key in good:
            changed = dict(good)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed", key)

    def test_skipped_signing_requires_negative_policy_and_no_signature(self):
        value = self.ready()
        value.update(status="signature_not_requested", signature_present=False, signature_valid=False,
                     sap_policy_matches=False, action_policy_matches=False)
        self.assertEqual(mod.clean(value)["status"], "signature_not_requested")
        for field in ("signature_present", "signature_valid", "sap_policy_matches", "action_policy_matches"):
            changed = dict(value, **{field: True})
            self.assertEqual(mod.clean(changed)["status"], "probe_failed", field)

    def test_wrong_types_and_unknown_error_values_are_rejected(self):
        result = mod.clean({"status": [], "signature_valid": 1, "error_domain": "SECRET", "error_code": True})
        for key in ("signature_valid", "error_domain", "error_code"):
            self.assertNotIn(key, result)

if __name__ == "__main__":
    unittest.main()
