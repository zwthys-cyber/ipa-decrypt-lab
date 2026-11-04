import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_asd_keybag as mod

class ASDFairPlayContracts(unittest.TestCase):
    def test_private_data_and_false_enrollment_claims_never_publish(self):
        result = mod.clean({"status": "service_request_failed", "dsid": "PRIVATE",
            "data": "PRIVATE", "error_domain": "PRIVATE", "description": "PRIVATE",
            "authorization_request_attempted": True, "keybag_import_attempted": True,
            "enrollment_created": True, "decryption_proven": True})
        self.assertNotIn("PRIVATE", json.dumps(result))
        for key in ("authorization_request_attempted", "keybag_import_attempted", "enrollment_created", "decryption_proven"):
            self.assertIs(result[key], False)

    def test_ready_requires_local_request_evidence(self):
        good = dict(status="synthetic_sync_ready", framework_loaded=True, service_class_present=True,
                    abi_verified=True, synthetic_request_attempted=True, synthetic_sync_present=True, error_present=False)
        self.assertEqual(mod.clean(good)["status"], "synthetic_sync_ready")
        for key in good:
            bad = dict(good)
            del bad[key]
            self.assertEqual(mod.clean(bad)["status"], "probe_failed")

    def test_error_classes_are_bounded_and_private_inputs_cannot_be_requested(self):
        result = mod.clean({"underlying_error_domain": "NSCocoaErrorDomain", "underlying_error_code": 4099,
            "error_mentions_entitlement": True, "error_mentions_permission": "PRIVATE",
            "underlying_description": "PRIVATE"})
        self.assertEqual(result["underlying_error_code"], 4099)
        self.assertNotIn("PRIVATE", json.dumps(result))
        with patch.object(mod.subprocess, "Popen") as process:
            self.assertEqual(mod.probe("123456789")["status"], "probe_failed")
            process.assert_not_called()

    def test_untrusted_types_and_values_are_omitted(self):
        for value in (None, [], "PRIVATE"):
            self.assertEqual(mod.clean(value)["status"], "probe_failed")
        result = mod.clean({"error_code": True, "error_domain": [], "synthetic_sync_present": 1,
                            "state_after": {"shared_sidb": True, "PRIVATE": "PRIVATE"}})
        self.assertNotIn("error_code", result)
        self.assertNotIn("error_domain", result)
        self.assertNotIn("synthetic_sync_present", result)
        self.assertEqual(result["state_after"], {"shared_sidb": True})

if __name__ == "__main__":
    unittest.main()
