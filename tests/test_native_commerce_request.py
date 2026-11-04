import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_commerce_request as mod

def sample():
    value = {key: True for key in mod.REQUIRED}
    value.update(schema=mod.SCHEMA, status="request_constructed", error_present=False, running_as_root=False)
    return value

class CommerceRequestContracts(unittest.TestCase):
    def test_construction_requires_identity_body_route_and_method_checks(self):
        original = sample()
        self.assertEqual(mod.clean(original)["status"], "request_constructed")
        for key in mod.REQUIRED | {"error_present", "running_as_root"}:
            value = dict(original)
            value.pop(key)
            self.assertEqual(mod.clean(value)["status"], "probe_failed", key)
        for key in ("request_host_allowed", "request_path_allowed", "request_is_post", "body_token_preserved"):
            value = dict(original, **{key: False})
            self.assertEqual(mod.clean(value)["status"], "probe_failed", key)

    def test_construction_never_claims_submission_or_decryption(self):
        value = sample()
        fields = ("account_login_attempted", "authorization_request_attempted",
                  "keybag_import_attempted", "enrollment_created", "decryption_proven")
        value.update({key: True for key in fields})
        result = mod.clean(value)
        for key in fields:
            self.assertIs(result[key], False)

    def test_credentials_identifiers_requests_and_body_are_not_published(self):
        value = sample()
        value.update(token="PRIVATE", guid="PRIVATE", request_url="PRIVATE", http_headers={"Cookie": "PRIVATE"},
            request_body="PRIVATE", machine_name="PRIVATE", native_phase="PRIVATE", native_exit_code=True)
        result = mod.clean(value)
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("native_phase", result)
        self.assertNotIn("native_exit_code", result)

    def test_schema_and_bad_types_fail_closed(self):
        for value in (None, [], {}, dict(sample(), schema="PRIVATE"), dict(sample(), status=[])):
            self.assertEqual(mod.clean(value)["status"], "probe_failed")
        self.assertEqual(mod.clean(dict(sample(), request_is_post=1))["status"], "probe_failed")

    def test_partial_results_preserve_only_bounded_phase_and_error(self):
        result = mod.clean(dict(schema=mod.SCHEMA, status="native_process_failed",
            native_phase="building_request", native_exit_code=-11, error_domain="PRIVATE", stderr="PRIVATE"))
        self.assertEqual(result["native_phase"], "building_request")
        self.assertEqual(result["native_exit_code"], -11)
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_binding_requires_every_identity_and_preservation_check(self):
        value = dict(sample(), status="synthetic_session_bound")
        value.update({key: True for key in mod.BINDING})
        self.assertEqual(mod.clean(value)["status"], "synthetic_session_bound")
        for key in mod.BINDING:
            changed = dict(value)
            changed.pop(key)
            self.assertEqual(mod.clean(changed)["status"], "probe_failed", key)
        self.assertFalse(mod.clean(value)["authorization_request_attempted"])

    def test_private_guid_handoff_is_strict_and_never_part_of_report(self):
        for code, output in ((0, b"PRIVATE"), (0, b"001122334455\n"), (1, b"001122334455")):
            with patch.object(mod, "run_private", return_value=(code, output, b"PRIVATE")):
                self.assertIsNone(mod.private_identity({}))
        with patch.object(mod, "run_private", return_value=(0, b"001122334455", b"PRIVATE")):
            handoff = json.loads(mod.private_identity({}))
            self.assertEqual(handoff["guid"], "001122334455")
            self.assertEqual(handoff["user_agent"], mod.LOGIN_AGENT)
            public = mod.clean(dict(sample(), **handoff))
            self.assertNotIn("001122334455", json.dumps(public))
            self.assertNotIn(mod.LOGIN_AGENT, json.dumps(public))

if __name__ == "__main__":
    unittest.main()
