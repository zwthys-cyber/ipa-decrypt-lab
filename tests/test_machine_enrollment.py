import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import machine_enrollment as mod

class MachineEnrollmentContracts(unittest.TestCase):
    def test_io_trace_is_bounded_and_never_emits_paths_or_payloads(self):
        cell = dict(area="shared_sc_info", operation="open", calls=3, failures=2,
                    last_errno=13, permission_failures=1, missing_failures=1)
        trace = dict(schema="bounded-import-io-v1", capped=False, entries=[cell])
        for key in ("io_trace", "initial_io_trace", "diversity_io_trace"):
            result = mod.clean({key: dict(trace, secret="PRIVATE",
                entries=[dict(cell, path="/PRIVATE", payload="PRIVATE")])})
            self.assertEqual(result[key], trace)
            self.assertNotIn("PRIVATE", json.dumps(result))
        invalid = [None, {}, dict(trace, capped=1), dict(trace, entries=[cell] * 39),
                   dict(trace, entries=[cell, cell]), dict(trace, entries=["PRIVATE"])]
        for field, bad in [("area", "PRIVATE"), ("operation", "PRIVATE"), ("calls", True),
                           ("calls", 100001), ("failures", 4), ("last_errno", 257),
                           ("permission_failures", 2), ("missing_failures", -1)]:
            invalid.append(dict(trace, entries=[dict(cell, **{field: bad})]))
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(mod.clean_io(value))
                self.assertNotIn("io_trace", mod.clean({"io_trace": value}))
        self.assertEqual(mod.clean_io(dict(trace, entries=[]))["entries"], [])

    def test_private_fields_never_publish(self):
        r = mod.clean({"status": "keybag_not_issued", "token": "SECRET", "dsid": "SECRET",
            "guid": "SECRET", "keybag": "SECRET", "error_domain": "SECRET", "description": "SECRET",
            "enrollment_created": True, "decryption_proven": True})
        self.assertNotIn("SECRET", json.dumps(r))
        self.assertFalse(r["enrollment_created"])
        self.assertFalse(r["decryption_proven"])

    def test_import_requires_observed_response_and_native_success(self):
        good = {"status": "keybag_imported_model_unverified", "http_status": 200,
            "authorization_request_attempted": True, "session_identity_verified": True, "body_token_bound": True,
            "keybag_present": True, "keybag_import_succeeded": True,
            "context_ready_before_request": True, "context_stable_before_import": True, "keybag_import_attempted": True,
            "diversitybag_present": False, "keybag_retry_attempted": False,
            "error_present": False, "apple_failure_present": False,
            "redirect_blocked": False, "response_oversized": False}
        self.assertEqual(mod.clean(good)["status"], "keybag_imported_model_unverified")
        for key in good:
            changed = dict(good)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed")

    def test_diversity_and_retry_cannot_hide_an_incomplete_import(self):
        good = dict(status="keybag_imported_model_unverified", http_status=200, authorization_request_attempted=True,
            session_identity_verified=True, body_token_bound=True, keybag_present=True, keybag_import_succeeded=True,
            context_ready_before_request=True, context_stable_before_import=True, keybag_import_attempted=True,
            diversitybag_present=True, diversity_import_attempted=True, diversity_import_succeeded=True,
            diversity_error_present=False, context_stable_after_diversity=True, keybag_retry_attempted=True,
            initial_import_succeeded=False, initial_import_fairplay_status=-42023,
            error_present=False, apple_failure_present=False, redirect_blocked=False, response_oversized=False)
        self.assertEqual(mod.clean(good)["status"], "keybag_imported_model_unverified")
        for key in ("diversity_import_attempted", "diversity_import_succeeded", "diversity_error_present",
                    "context_stable_after_diversity", "initial_import_succeeded", "initial_import_fairplay_status"):
            changed = dict(good)
            del changed[key]
            self.assertEqual(mod.clean(changed)["status"], "probe_failed")
        changed = dict(good, diversitybag_present=False)
        self.assertEqual(mod.clean(changed)["status"], "probe_failed")
        private = mod.clean({"initial_error_domain": "PRIVATE", "diversity_error_domain": "PRIVATE",
            "diversity_import_fairplay_status": True, "initial_import_fairplay_status": 2**31,
            "diversitybag": "PRIVATE"})
        self.assertNotIn("PRIVATE", json.dumps(private))
        self.assertNotIn("diversity_import_fairplay_status", private)

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
            self.assertEqual(mod.trial("login", "native", client_context="unrecognized")["status"], "invalid_private_input")
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
                            "login_provisioning": {"login_md_action_present": True, "login_md_provision_requested": False, "raw_header": "SECRET"},
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
                self.assertIs(result["login_md_action_present"], True)
                self.assertIs(result["login_md_provision_requested"], False)
                self.assertNotIn("SECRET", json.dumps(result))

    def test_response_challenges_publish_only_fixed_action_classes_and_flags(self):
        for action in ("none", "SP", "SM", "RP", "other"):
            r = mod.clean({"status": "keybag_not_issued", "md_action": action,
                "amd_action": action, "md_data_present": True, "md_data_valid": False,
                "amd_data_present": True, "amd_data_valid": True,
                "response_headers": {"Set-Cookie": "SECRET"}, "md_data": "SECRET"})
            self.assertEqual(r["md_action"], action)
            self.assertEqual(r["amd_action"], action)
            self.assertNotIn("SECRET", json.dumps(r))
        r = mod.clean({"md_action": "SECRET", "amd_action": [], "md_data_valid": 1})
        for key in ("md_action", "amd_action", "md_data_valid"):
            self.assertNotIn(key, r)

    def test_login_summary_rejects_private_text_and_non_boolean_values(self):
        r = mod.clean_login_summary({"login_md_action_present": True, "login_md_data_valid": 1,
            "login_amd_data_present": "SECRET", "raw_headers": "SECRET"})
        self.assertEqual(r, {"login_md_action_present": True})
        for invalid in (None, [], "SECRET"):
            self.assertEqual(mod.clean_login_summary(invalid), {})

    def test_login_client_agent_is_explicitly_selected_and_verified(self):
        for mode in ("native", "login_agent"):
            for bound in (True, False):
                def fake_run(argv, env, **kwargs):
                    if argv[0] == "login":
                        handoff = Path(env["LAB_ENROLLMENT_INPUT_PATH"])
                        handoff.write_text(json.dumps({"dsid": "123", "token": "SECRET", "guid": "001122334455",
                            "user_agent": "private-client/1", "unexpected": "SECRET"}))
                        handoff.chmod(0o600)
                    else:
                        payload = json.loads(kwargs["data"])
                        if mode == "login_agent":
                            self.assertEqual(payload["user_agent"], "private-client/1")
                            self.assertEqual(payload["client_context"], mode)
                        else:
                            self.assertNotIn("user_agent", payload)
                            self.assertNotIn("client_context", payload)
                        self.assertNotIn("unexpected", payload)
                        Path(argv[1]).write_text(json.dumps({"status": "keybag_not_issued",
                            "authorization_request_attempted": True, "client_agent_bound": bound}))
                    return (0, b"", b"")
                with patch.dict("os.environ", {"APPLE_ID": "test@example.invalid", "APPLE_PASSWORD": "SECRET"}, clear=True):
                    with patch.object(mod, "run_private", side_effect=fake_run):
                        result = mod.trial("login", "native", client_context=mode)
                expected = "probe_failed" if mode == "login_agent" and not bound else "keybag_not_issued"
                self.assertEqual(result["status"], expected)
                self.assertNotIn("private-client/1", json.dumps(result))
                self.assertNotIn("SECRET", json.dumps(result))

    def test_import_status_is_a_bounded_integer_without_error_text(self):
        for status in (-42000, -(2**31), 2**31-1):
            result = mod.clean({"status": "keybag_import_failed", "import_fairplay_status": status,
                                "failure_reason": "PRIVATE", "keybag": "PRIVATE"})
            self.assertEqual(result["import_fairplay_status"], status)
            self.assertNotIn("PRIVATE", json.dumps(result))
        for invalid in (True, str(-42000), -(2**31)-1, 2**31):
            self.assertNotIn("import_fairplay_status", mod.clean({"import_fairplay_status": invalid}))

    def test_keybag_shape_never_reports_bytes_or_unbounded_labels(self):
        result = mod.clean({"keybag_size_bucket": "under_256", "keybag_gzip": False,
            "keybag_base64_text": True, "keybag_binary_plist": False, "keybag_xml": False,
            "keybag": "PRIVATE", "keybag_prefix": "PRIVATE"})
        self.assertEqual(result["keybag_size_bucket"], "under_256")
        self.assertIs(result["keybag_base64_text"], True)
        self.assertNotIn("PRIVATE", json.dumps(result))
        result = mod.clean({"keybag_size_bucket": "PRIVATE", "keybag_gzip": 1})
        self.assertNotIn("keybag_size_bucket", result)
        self.assertNotIn("keybag_gzip", result)

    def test_boolean_numbers_and_unknown_types_rejected(self):
        r = mod.clean({"status": [], "error_domain": [], "error_code": True,
                       "keybag_import_succeeded": 1, "http_status": True})
        for key in ("error_domain", "error_code", "keybag_import_succeeded", "http_status"):
            self.assertNotIn(key, r)

if __name__ == "__main__":
    unittest.main()
