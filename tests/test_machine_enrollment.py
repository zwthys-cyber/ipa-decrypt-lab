import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import machine_enrollment as mod

class MachineEnrollmentContracts(unittest.TestCase):
    def test_private_fields_never_publish(self):
        r = mod.clean({"status": "keybag_not_issued", "token": "SECRET", "dsid": "SECRET",
            "guid": "SECRET", "keybag": "SECRET", "error_domain": "SECRET", "description": "SECRET",
            "enrollment_created": True, "decryption_proven": True})
        self.assertNotIn("SECRET", json.dumps(r))
        self.assertFalse(r["enrollment_created"])
        self.assertFalse(r["decryption_proven"])

    def test_import_requires_observed_response_and_native_success(self):
        good = {"status": "keybag_imported_model_unverified", "http_status": 200,
            "authorization_request_attempted": True, "session_identity_verified": True,
            "keybag_present": True, "keybag_import_succeeded": True,
            "error_present": False, "apple_failure_present": False,
            "redirect_blocked": False, "response_oversized": False}
        self.assertEqual(mod.clean(good)["status"], "keybag_imported_model_unverified")
        for key in good:
            changed = dict(good)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed")

    def test_redirect_or_failure_cannot_become_success(self):
        self.assertEqual(mod.clean({"status": "keybag_imported_model_unverified",
            "redirect_blocked": True, "http_status": 200})["status"], "probe_failed")

    def test_missing_credentials_prevents_any_process(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(mod, "run_private") as run:
            self.assertEqual(mod.trial("login", "native")["status"], "missing_credentials")
            run.assert_not_called()

    def test_login_failure_stops_before_native_authorization(self):
        with patch.dict("os.environ", {"APPLE_ID": "test@example.invalid", "APPLE_PASSWORD": "SECRET"}, clear=True):
            with patch.object(mod, "run_private", return_value=(1, b"", b"apple_auth_ambiguous_bad_login")) as run:
                result = mod.trial("login", "native")
                self.assertEqual(result["status"], "login_ambiguous")
                self.assertEqual(run.call_count, 1)
                self.assertNotIn("SECRET", json.dumps(result))
                self.assertNotIn("SECRET", str(run.call_args.args[0]))

    def test_invalid_purpose_stops_before_credentials_or_processes(self):
        with patch.object(mod, "run_private") as run:
            self.assertEqual(mod.trial("login", "native", purpose="unrecognized")["status"], "invalid_private_input")
            self.assertEqual(mod.trial("login", "native", session_context="unrecognized")["status"], "invalid_private_input")
            run.assert_not_called()

    def test_session_context_selects_only_the_requested_private_fields(self):
        expected_fields = {
            "token": {"dsid", "token", "guid"},
            "cookies": {"dsid", "token", "guid", "cookies"},
            "storefront": {"dsid", "token", "guid", "storefront"},
            "store": {"dsid", "token", "guid", "cookies", "storefront"},
        }
        for context, fields in expected_fields.items():
            with self.subTest(context=context):
                def fake_run(argv, env, **kwargs):
                    if argv[0] == "login":
                        self.assertEqual(env["LAB_AUTHORIZATION_PURPOSE"], "machineAuthorize")
                        handoff = Path(env["LAB_ENROLLMENT_INPUT_PATH"])
                        handoff.write_text(json.dumps({"dsid": "123", "token": "SECRET", "guid": "001122334455",
                            "cookies": [{"name": "private", "value": "SECRET"}], "storefront": "SECRET",
                            "unexpected_private_field": "SECRET"}))
                        handoff.chmod(0o600)
                    else:
                        payload = json.loads(kwargs["data"])
                        self.assertEqual(set(payload), fields)
                        self.assertNotIn("APPLEPACKAGE_PASSWORD", env)
                        Path(argv[1]).write_text(json.dumps({"status": "keybag_not_issued", "http_status": 200}))
                    return (0, b"", b"")
                with patch.dict("os.environ", {"APPLE_ID": "reader@example.invalid", "APPLE_PASSWORD": "SECRET"}, clear=True):
                    with patch.object(mod, "run_private", side_effect=fake_run) as run:
                        result = mod.trial("login", "native", purpose="machineAuthorize", session_context=context)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(result["authentication_purpose"], "machineAuthorize")
                self.assertEqual(result["session_context"], context)
                self.assertNotIn("SECRET", json.dumps(result))

    def test_boolean_numbers_and_unknown_types_rejected(self):
        r = mod.clean({"status": [], "error_domain": [], "error_code": True,
                       "keybag_import_succeeded": 1, "http_status": True})
        for key in ("error_domain", "error_code", "keybag_import_succeeded", "http_status"):
            self.assertNotIn(key, r)

if __name__ == "__main__":
    unittest.main()
