import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import machine_enrollment as enrollment
import store_account_summary as account


class ObservedEnrollmentTests(unittest.TestCase):
    def fake_run(self, argv, env, **kwargs):
        if argv[0] == "login":
            path = Path(env["LAB_ENROLLMENT_INPUT_PATH"])
            path.write_text(json.dumps(dict(dsid="1234567", token="PRIVATE_SYNTHETIC",
                guid="001122334455", storefront="143441-1", user_agent="Synthetic/1", cookies=[])))
            path.chmod(0o600)
        else:
            Path(argv[-1]).write_text(json.dumps(dict(schema="ipa-lab-machine-enrollment-v1",
                status="keybag_not_issued", authorization_request_attempted=True)))
        return 0, b"PRIVATE_SYNTHETIC_STDOUT", b"PRIVATE_SYNTHETIC_STDERR"

    def perform(self, counts, state=None, fake=None):
        state = {"root_status":"observed"} if state is None else state
        with patch.dict(os.environ, {"APPLE_ID":"reader@example.invalid", "APPLE_PASSWORD":"PRIVATE_SYNTHETIC"}), \
                patch.object(enrollment, "run_private", side_effect=fake or self.fake_run) as process, \
                patch.object(enrollment, "observed_count", side_effect=counts) as count, \
                patch.object(enrollment, "observe_state_safely", return_value=state) as observer:
            result = enrollment.trial("login", "native", observe_state=True)
        return result, process, count, observer

    def test_unknown_count_stops_before_native_authorization(self):
        result, process, _, observer = self.perform([None])
        self.assertEqual(result["status"], "account_count_unavailable")
        self.assertFalse(result["authorization_request_attempted"])
        self.assertEqual(process.call_count, 1)
        observer.assert_not_called()

    def test_full_quota_stops_before_native_authorization(self):
        result, process, _, observer = self.perform([5])
        self.assertEqual(result["status"], "computer_quota_full")
        self.assertEqual(result["account_count_before"], 5)
        self.assertFalse(result["authorization_request_attempted"])
        self.assertEqual(process.call_count, 1)
        observer.assert_not_called()

    def test_root_observation_must_work_before_native_authorization(self):
        result, process, _, observer = self.perform([1], {"root_status":"unavailable"})
        self.assertEqual(result["status"], "state_observer_unavailable")
        self.assertFalse(result["authorization_request_attempted"])
        self.assertEqual(process.call_count, 1)
        observer.assert_called_once()

    def test_before_and_after_counts_and_observations_are_recorded(self):
        result, process, count, observer = self.perform([1,2])
        self.assertEqual(result["status"], "keybag_not_issued")
        self.assertEqual((result["account_count_before"], result["account_count_after"]), (1,2))
        self.assertTrue(result["account_count_after_observed"])
        self.assertEqual(process.call_count, 2)
        self.assertEqual(count.call_count, 2)
        self.assertEqual(observer.call_count, 2)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_native_timeout_still_observes_actual_post_state_without_retry(self):
        def run(argv, env, **kwargs):
            if argv[0] == "native":
                raise subprocess.TimeoutExpired(argv, 75)
            return self.fake_run(argv, env, **kwargs)
        result, process, _, observer = self.perform([1,2], fake=run)
        self.assertEqual(result["status"], "native_timeout")
        self.assertEqual(result["account_count_after"], 2)
        self.assertEqual(process.call_count, 2)
        self.assertEqual(observer.call_count, 2)

    def test_missing_after_count_is_explicit_not_zero(self):
        result, _, _, _ = self.perform([1,None])
        self.assertFalse(result["account_count_after_observed"])
        self.assertNotIn("account_count_after", result)

    def test_observed_count_requires_explicit_success_and_real_integer(self):
        value=dict(status="computer_count_observed", computer_count_observed=True,
                   store_session_authenticated=True, http_status=200, authorized_computers=2)
        with patch.object(account, "fetch_summary", return_value=value):
            self.assertEqual(enrollment.observed_count({}), 2)
        for change in ({"authorized_computers": True}, {"authorized_computers":"2"}, {"http_status":401},
                       {"store_session_authenticated":False}, {"status":"graphql_errors"}):
            with patch.object(account, "fetch_summary", return_value=dict(value, **change)):
                self.assertIsNone(enrollment.observed_count({}))

    def test_diversity_requirement_is_distinct_from_import_success(self):
        result=enrollment.clean({"status":"keybag_not_issued", "need_diversitybag":True})
        self.assertTrue(result["need_diversitybag"])
        self.assertFalse(result["enrollment_created"])


if __name__ == "__main__":
    unittest.main()
