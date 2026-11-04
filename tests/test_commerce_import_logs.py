from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import commerce_import_logs as mod

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(seconds=5)

def event(message, process="commerce", when=None):
    return json.dumps(dict(processImagePath="/PRIVATE/" + process,
        timestamp=(when or START + timedelta(seconds=1)).isoformat(),
        eventMessage=message, activityIdentifier="PRIVATE"))

class CommerceLogContracts(unittest.TestCase):
    def test_raw_identity_and_unknown_numeric_values_never_escape(self):
        raw = event("Unable to import keybag error=-42023 PRIVATE account=999888777 cookie=PRIVATE")
        result = mod.summarize(raw, START, END)
        self.assertEqual(result["known_error_codes"], [-42023])
        self.assertEqual(result["rejection_mentions"], 1)
        self.assertFalse(result["import_verified"])
        for private in ("PRIVATE", "999888777", "cookie", "Unable"):
            self.assertNotIn(private, json.dumps(result))

    def test_exact_process_and_precise_time_are_required(self):
        raw = "\n".join([
            event("import keybag failed -42023", process="other"),
            event("import keybag failed -42023", when=START-timedelta(microseconds=1)),
            event("import keybag failed -42023", when=END+timedelta(microseconds=1)),
            event("import keybag failed -42018", process="fpsd"),
        ])
        result = mod.summarize(raw, START, END)
        self.assertEqual(result["matched_events"], 1)
        self.assertEqual(result["known_error_codes"], [-42018])

    def test_success_wording_is_not_verification(self):
        result = mod.summarize(event("import keybag succeeded PRIVATE"), START, END)
        self.assertEqual(result["import_mentions"], 1)
        self.assertEqual(result["rejection_mentions"], 0)
        self.assertFalse(result["import_verified"])

    def test_absent_malformed_and_oversized_logs_provide_no_positive_evidence(self):
        for raw in ("", "PRIVATE", "[]", event("unrelated PRIVATE"),
                    json.dumps(dict(processImagePath="/commerce", timestamp="bad", eventMessage="import keybag"))):
            self.assertEqual(mod.summarize(raw, START, END)["status"], "no_matching_events")
        self.assertEqual(mod.summarize("x"*(mod.MAX_OUTPUT+1), START, END)["status"], "output_limit")

    def test_log_command_failure_and_timeout_fail_closed(self):
        with patch.object(mod, "run_private", return_value=(1, b"PRIVATE", b"PRIVATE")):
            result = mod.collect(START, END)
            self.assertEqual(result["status"], "log_unavailable")
            self.assertNotIn("PRIVATE", json.dumps(result))
        with patch.object(mod, "run_private", side_effect=subprocess.TimeoutExpired("log", 15)):
            self.assertEqual(mod.collect(START, END)["status"], "log_timeout")
        with patch.object(mod, "run_private") as run:
            self.assertEqual(mod.collect(START, START+timedelta(seconds=61))["status"], "invalid_window")
            run.assert_not_called()

if __name__ == "__main__":
    unittest.main()
