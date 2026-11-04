import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_commerce_keybag as mod

class CommerceContracts(unittest.TestCase):
    def test_secrets_and_native_claims_are_not_published(self):
        result = mod.clean(dict(status="service_request_failed", token="PRIVATE", sync_data="PRIVATE",
            dsid="PRIVATE", description="PRIVATE", account_login_attempted=True,
            authorization_request_attempted=True, keybag_import_attempted=True,
            enrollment_created=True, decryption_proven=True, error_domain="PRIVATE",
            underlying_error_domain="PRIVATE"))
        self.assertNotIn("PRIVATE", json.dumps(result))
        for key in ("account_login_attempted", "authorization_request_attempted", "keybag_import_attempted",
                    "enrollment_created", "decryption_proven"):
            self.assertIs(result[key], False)

    def test_success_requires_reply_data_identity_and_no_error(self):
        good = dict(status="synthetic_sync_ready", framework_loaded=True, service_class_present=True,
            synthetic_account_verified=True, abi_verified=True, synthetic_request_attempted=True,
            reply_received=True, service_success=True, synthetic_sync_present=True,
            error_present=False, transport_error_received=False, need_diversitybag=True, transaction_type=2)
        self.assertEqual(mod.clean(good)["status"], "synthetic_sync_ready")
        for key in good:
            changed = dict(good)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed", key)
        for key in ("error_present", "transport_error_received"):
            self.assertEqual(mod.clean(dict(good, **{key: True}))["status"], "probe_failed")

    def test_types_bounds_and_state_allowlist(self):
        result = mod.clean(dict(status=[], error_code=True, underlying_error_code=1000000,
            framework_loaded=1, native_exit_code=True, transaction_type=True, state_after={"shared_sidb": True, "PRIVATE": "PRIVATE"}))
        for key in ("error_code", "underlying_error_code", "framework_loaded", "transaction_type", "native_exit_code"):
            self.assertNotIn(key, result)
        self.assertEqual(result["state_after"], {"shared_sidb": True})
        self.assertNotIn("PRIVATE", json.dumps(result))
        for malformed in (None, [], "PRIVATE"):
            self.assertEqual(mod.clean(malformed)["status"], "probe_failed")

    def test_crash_diagnostics_only_publish_phase_signal_and_flags(self):
        result = mod.clean(dict(status="native_process_failed", native_exit_code=-6,
            native_phase="loading_framework", process_mentions_assertion=True,
            stderr="PRIVATE", stdout="PRIVATE", process_mentions_bundle=1))
        self.assertEqual(result["native_exit_code"], -6)
        self.assertEqual(result["native_phase"], "loading_framework")
        self.assertNotIn("process_mentions_bundle", result)
        self.assertNotIn("PRIVATE", json.dumps(result))
        for invalid in ("PRIVATE", [], None):
            self.assertNotIn("native_phase", mod.clean({"native_phase": invalid}))

    def test_loader_and_service_errors_are_only_fixed_metadata(self):
        result = mod.clean(dict(status="framework_unavailable", loader_mentions_missing=True,
            loader_mentions_architecture=False, loader_mentions_signature=False, dlerror="PRIVATE",
            error_domain="NSCocoaErrorDomain", error_code=4099, error_mentions_connection=True))
        self.assertTrue(result["loader_mentions_missing"])
        self.assertEqual(result["error_code"], 4099)
        self.assertNotIn("PRIVATE", json.dumps(result))

if __name__ == "__main__":
    unittest.main()
