import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_commerce_import as mod

def sample(fixture="invalid-both"):
    reply = dict(status="synthetic_sync_ready", reply_received=True, service_success=True,
        synthetic_sync_present=True, need_diversitybag=True, error_present=False)
    return dict(schema=mod.SCHEMA, fixture=fixture,
        status="submission_unverified" if fixture == "invalid-both" else "baseline_complete",
        running_as_root=False, framework_loaded=True, synthetic_account_verified=True,
        sync_abi_verified=True, import_abi_verified=True, transport_error_received=False,
        keybag_import_attempted=fixture == "invalid-both", import_call_returned=fixture == "invalid-both",
        baseline=copy.deepcopy(reply), followup=copy.deepcopy(reply),
        state_before={key: False for key in mod.STATE_KEYS},
        state_after={key: False for key in mod.STATE_KEYS})

class CommerceImportContracts(unittest.TestCase):
    def test_submission_and_changed_files_never_prove_import(self):
        value = sample()
        value.update(import_verified=True, enrollment_created=True, decryption_proven=True)
        value["state_after"] = {key: True for key in mod.STATE_KEYS}
        result = mod.clean(value, "invalid-both")
        self.assertEqual(result["status"], "submission_unverified")
        for key in ("import_verified", "enrollment_created", "decryption_proven"):
            self.assertIs(result[key], False)

    def test_complete_observation_requires_both_replies_and_transport(self):
        original = sample()
        self.assertEqual(mod.clean(original, "invalid-both")["status"], "submission_unverified")
        for key in ("framework_loaded", "synthetic_account_verified", "sync_abi_verified",
                "import_abi_verified", "running_as_root", "transport_error_received",
                "keybag_import_attempted", "import_call_returned", "baseline", "followup",
                "state_before", "state_after"):
            value = copy.deepcopy(original)
            value.pop(key)
            self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed", key)
        for key in mod.READY_FLAGS + ("error_present", "need_diversitybag"):
            value = copy.deepcopy(original)
            value["followup"].pop(key)
            self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed", key)

    def test_fixture_confusion_and_forged_success_fail_closed(self):
        for fixture in ("baseline", "invalid-both"):
            self.assertNotEqual(mod.clean(sample(fixture), fixture)["status"], "probe_failed")
        self.assertEqual(mod.clean(sample(), "baseline")["status"], "probe_failed")
        self.assertEqual(mod.clean(sample(), "PRIVATE")["status"], "probe_failed")
        value = sample()
        value["status"] = "import_succeeded"
        self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed")
        value = sample("baseline")
        value["keybag_import_attempted"] = True
        self.assertEqual(mod.clean(value, "baseline")["status"], "probe_failed")

    def test_private_values_and_bad_types_are_not_published(self):
        value = sample()
        value.update(token="PRIVATE", keybag="PRIVATE", dsid="PRIVATE",
            error_domain="PRIVATE", error_code=True, native_exit_code=True, native_phase="PRIVATE")
        value["followup"].update(sync_data="PRIVATE", description="PRIVATE", underlying_error_domain="PRIVATE")
        value["state_after"]["PRIVATE"] = "PRIVATE"
        result = mod.clean(value, "invalid-both")
        self.assertNotIn("PRIVATE", json.dumps(result))
        for key in ("error_code", "native_exit_code", "native_phase"):
            self.assertNotIn(key, result)

    def test_errors_and_timeout_cannot_be_positive_observations(self):
        for key in ("baseline", "followup"):
            value = sample()
            value[key]["error_present"] = True
            self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed")
            value[key] = {"status": "service_reply_timeout"}
            self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed")
        value = sample()
        value["transport_error_received"] = True
        self.assertEqual(mod.clean(value, "invalid-both")["status"], "probe_failed")

if __name__ == "__main__":
    unittest.main()
