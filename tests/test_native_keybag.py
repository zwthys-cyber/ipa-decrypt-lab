import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("native_keybag", Path(__file__).parents[1] / "tools/native_keybag.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class NativeKeybagContracts(unittest.TestCase):
    def test_never_publish_unrecognized_fields_or_claim_model(self):
        r = mod.clean({"status": "context_ready", "account_login_attempted": True,
            "enrollment_created": True, "decryption_proven": True,
            "password": "SECRET", "error_domain": "SECRET", "error_code": "SECRET",
            "description": "SECRET", "state_after": {"shared_sidb": True, "SECRET": True}})
        self.assertNotIn("SECRET", json.dumps(r))
        self.assertFalse(r["enrollment_created"])
        self.assertFalse(r["account_login_attempted"])
        self.assertFalse(r["decryption_proven"])
        self.assertEqual(r["status"], "probe_failed")

    def test_readiness_requires_error_free_abi_and_data(self):
        valid = {"status": "synthetic_sync_ready", "abi_verified": True,
            "sync_data_present": True, "synthetic_account_id": True, "transaction_type": 1,
            "sync_data_length": 123, "error_present": False}
        self.assertEqual(mod.clean(valid)["status"], "synthetic_sync_ready")
        for key in valid:
            changed = dict(valid)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed")

    def test_metadata_allows_only_known_methods_and_type_encodings(self):
        r = mod.clean({"interfaces": {"ACAccount": {"present": True, "methods": {
            "-ams_DSID": "@16@0:8", "-ams_password": "SECRET", "SECRET": "@16@0:8"}},
            "SECRET": {"present": True}}, "bag_keys": {"AMSBagKeyAuthorizeMachineURL": "SECRET"}})
        self.assertNotIn("SECRET", json.dumps(r))
        self.assertEqual(r["interfaces"]["ACAccount"]["methods"]["-ams_DSID"], "@16@0:8")
        self.assertNotIn("-ams_password", r["interfaces"]["ACAccount"]["methods"])

    def test_environment_has_no_account_secrets(self):
        with patch.dict("os.environ", {"APPLE_ID": "SECRET", "APPLE_PASSWORD": "SECRET"}):
            self.assertEqual(set(mod.environment()), {"PATH", "GITHUB_ACTIONS"})

    def test_timeout_is_bounded_and_private_output_discarded(self):
        with patch.object(mod.subprocess, "run", side_effect=subprocess.TimeoutExpired("cmd", 20)) as run:
            r = mod.probe("kbsync")
        self.assertEqual(r["status"], "probe_timeout")
        self.assertEqual(run.call_args.kwargs["timeout"], 20)
        self.assertIs(run.call_args.kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(run.call_args.kwargs["stderr"], subprocess.DEVNULL)

    def test_native_error_does_not_become_success(self):
        with patch.object(mod.subprocess, "run") as run:
            run.return_value.returncode = -9
            r = mod.probe("context")
        self.assertEqual(r["status"], "native_process_failed")
        self.assertEqual(r["native_exit_code"], -9)

    def test_parameters_require_ephemeral_synthetic_identity(self):
        value = {"status": "synthetic_parameters_ready", "sync_data_length": 200,
                 "error_present": False}
        for key in ("abi_verified", "ephemeral_account", "sync_data_present", "guid_is_six_bytes",
                    "owner_is_synthetic", "machine_name_present", "parameter_names_valid", "x_token_is_zero"):
            value[key] = True
        self.assertEqual(mod.clean(value)["status"], "synthetic_parameters_ready")
        for key in value:
            broken = dict(value)
            del broken[key]
            self.assertEqual(mod.clean(broken)["status"], "probe_failed")

    def test_url_report_excludes_query_credentials_and_unknown_hosts(self):
        r = mod.clean({"endpoint_host": "secret.example", "endpoint_path": "/secret",
            "endpoint_url": "https://user:secret@buy.itunes.apple.com/?secret",
            "endpoint_query": "secret"})
        self.assertNotIn("secret", json.dumps(r))
        good = mod.clean({"endpoint_host": "buy.itunes.apple.com",
            "endpoint_path": "/WebObjects/MZFinance.woa/wa/authorizeMachine"})
        self.assertEqual(good["endpoint_host"], "buy.itunes.apple.com")

    def test_native_numeric_booleans_remain_rejected(self):
        r = mod.clean({"status": "context_ready", "abi_verified": 1, "context_ready": 1,
            "error_present": 0, "interfaces": {"AMSKeybag": {"present": 1}}})
        self.assertEqual(r["status"], "probe_failed")
        self.assertNotIn("abi_verified", r)
        self.assertEqual(r["interfaces"], {})

    def test_constructed_request_is_not_authorization(self):
        value = {"status": "synthetic_request_ready", "error_present": False}
        for key in ("abi_verified", "ephemeral_account", "request_present", "request_is_post",
                    "request_body_is_plist", "x_token_is_zero", "owner_is_synthetic", "endpoint_supported",
                    "session_policy_verified", "session_headers_applied", "token_header_is_synthetic", "redirect_policy_verified", "cookie_policy_verified"):
            value[key] = True
        r = mod.clean(value)
        self.assertEqual(r["status"], "synthetic_request_ready")
        self.assertFalse(r["enrollment_created"])
        for key in value:
            broken = dict(value)
            del broken[key]
            self.assertEqual(mod.clean(broken)["status"], "probe_failed")

    def test_public_route_reports_only_fixed_classifications(self):
        result = mod.classify_route("https://buy.itunes.apple.com/commerce/machine/authorize/?token=SECRET")
        self.assertEqual(result["redirect_path"], "authorize_slash")
        self.assertTrue(result["redirect_query_present"])
        self.assertNotIn("SECRET", json.dumps(result))
        for value in ("https://buy.itunes.apple.com.evil.invalid/SECRET",
                      "https://user:SECRET@buy.itunes.apple.com:444/SECRET", None):
            self.assertNotIn("SECRET", json.dumps(mod.classify_route(value)))

    def test_bad_types_fail_closed(self):
        for value in (None, [], "SECRET"):
            self.assertEqual(mod.clean(value)["status"], "probe_failed")
        r = mod.clean({"status": [], "mode": {}, "error_domain": [], "transaction_type": True,
                       "sync_data_length": True, "error_code": True})
        self.assertNotIn("transaction_type", r)
        self.assertNotIn("sync_data_length", r)
        self.assertNotIn("error_code", r)

if __name__ == "__main__":
    unittest.main()
