import contextlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_auth_diagnostics as diagnostics

class NativeAuthDiagnosticsTests(unittest.TestCase):
    def event(self, message, process="appstoreagent"):
        return {"processImagePath": "/System/private/path/" + process, "eventMessage": message,
                "private-account": "never-export", "timestamp": "private-time"}

    def test_nested_errors_export_only_fixed_domains_and_codes(self):
        message = ('Login failed for private@example.invalid password=private-password '
                   'Error Domain=ASDErrorDomain Code=500 "private-dialog" '
                   'underlying Error Domain=AMSErrorDomain Code=301 '
                   'HTTPStatusCode=403 failureType="5002" token=private-token')
        result = diagnostics.summarize(json.dumps([self.event(message)]))
        self.assertEqual(result["capture_status"], "ok")
        self.assertEqual({(r["kind"], r["domain_or_symbol"], r["code"]) for r in result["records"]},
                         {("error", "ASDErrorDomain", 500), ("error", "AMSErrorDomain", 301),
                          ("http", "", 403), ("failure_type", "", 5002)})
        self.assertTrue(all(r["authentication_context"] for r in result["records"]))
        output = json.dumps(result)
        for secret in ("private", "example.invalid", "password", "token", "never-export"):
            self.assertNotIn(secret, output)

    def test_unknown_processes_domains_and_long_identifiers_are_dropped(self):
        values = [self.event("Error Domain=NSURLErrorDomain Code=-1009", "private-process"),
                  self.event("Error Domain=PrivateDomain Code=123"),
                  self.event("Error Domain=AMSErrorDomain Code=123456789 failureType=987654321 "
                             "HTTPStatusCode=40312345 dsid=123456789"),
                  {"process": ["App Store"], "eventMessage": "private"}]
        result = diagnostics.summarize(json.dumps(values))
        self.assertEqual(result["records"], [])

    def test_error_variants_symbols_are_deduplicated_and_counted(self):
        message = ("Authentication: AMSErrorDomain error 301 Error Domain=AMSErrorDomain Code=301 "
                   "MZFinance.BadLogin.Configurator_message")
        result = diagnostics.summarize(json.dumps([self.event(message), self.event(message)]))
        self.assertEqual(len(result["records"]), 2)
        self.assertTrue(all(r["events"] == 2 for r in result["records"]))
        self.assertEqual([r["domain_or_symbol"] for r in result["records"] if r["kind"] == "symbol"],
                         ["MZFinance.BadLogin.Configurator_message"])

    def test_underlying_domains_and_fixed_reason_flags_share_one_event(self):
        message = ('Attempting to show login error: Error Domain=AKAuthenticationError Code=-7018 '
                   'NSUnderlyingError={Error Domain=com.apple.AppleIDAuthSupport Code=2 '
                   'NSDescription=private-password}; selected protocol key missing; user=private-email')
        result = diagnostics.summarize(json.dumps([self.event(message, "akd")]))
        self.assertEqual(result["reason_records"],
                         [{"process": "akd", "reason_flag": "selected_protocol_missing", "events": 1}])
        self.assertEqual(result["cooccurrences"], [{
            "process": "akd", "errors": [{"domain": "AKAuthenticationError", "code": -7018},
                                       {"domain": "com.apple.AppleIDAuthSupport", "code": 2}],
            "reason_flags": ["selected_protocol_missing"], "events": 1,
        }])
        self.assertNotIn("private", json.dumps(result))

    def test_separate_events_cannot_become_an_underlying_error_chain(self):
        result = diagnostics.summarize(json.dumps([
            self.event("Error Domain=AKAuthenticationError Code=-7018", "akd"),
            self.event("Error Domain=com.apple.AppleIDAuthSupport Code=2", "akd"),
            self.event("selected protocol key missing; private context", "akd"),
        ]))
        self.assertEqual(result["cooccurrences"], [])
        self.assertEqual(len(result["reason_records"]), 1)

    def test_complex_events_do_not_create_unbounded_error_groups(self):
        message = " ".join("Error Domain=AKAuthenticationError Code=" + str(i) for i in range(100))
        result = diagnostics.summarize(json.dumps([self.event(message, "akd")]))
        self.assertEqual(result["complex_events_skipped"], 1)
        self.assertEqual(result["cooccurrences"], [])
        self.assertEqual(len(result["records"]), 64)
        self.assertTrue(result["record_limit_reached"])

    def test_invalid_and_oversized_input_cannot_emit_raw_data(self):
        for raw in (b"private-invalid-json", b"{}", None):
            self.assertNotEqual(diagnostics.summarize(raw)["capture_status"], "ok")
        with patch.object(diagnostics, "MAX_EVENTS", 1):
            self.assertEqual(diagnostics.summarize("[{}, {}]")["capture_status"], "event_limit_or_invalid_log")
        result = diagnostics.summarize(json.dumps([self.event("private" * 10000)]))
        self.assertEqual(result["oversized_events_skipped"], 1)
        self.assertEqual(result["records"], [])

    def test_child_output_and_runtime_are_bounded_and_fail_closed(self):
        cases = [
            ("import sys;sys.stdout.write('x'*8192)", 1, 100, "limit_reached"),
            ("import time;time.sleep(3)", 0.05, 100, "timeout"),
            ("import sys;sys.stdout.write('private');sys.exit(2)", 1, 100, "log_command_failed"),
        ]
        for source, timeout, limit, expected in cases:
            with self.subTest(expected=expected):
                state, output = diagnostics.capture([sys.executable, "-c", source], timeout=timeout, limit=limit)
                self.assertEqual(state, expected)
                self.assertEqual(output, b"")

    def test_child_does_not_receive_credentials_or_publish_stderr(self):
        with patch.dict(os.environ, {"APPLE_PASSWORD": "private-password"}):
            state, raw = diagnostics.capture([sys.executable, "-c",
                "import os,sys;sys.stderr.write('private-error');print('APPLE_PASSWORD' in os.environ)"])
        self.assertEqual(state, "ok")
        self.assertEqual(raw.strip(), b"False")

    def test_collection_guard_and_time_window_precede_log_execution(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(diagnostics, "capture") as capture:
            self.assertEqual(diagnostics.collect(1)["capture_status"], "requires_github_macos")
            capture.assert_not_called()
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), patch.object(
            diagnostics.sys, "platform", "darwin"
        ), patch.object(diagnostics, "capture", return_value=("ok", b"[]")) as capture:
            self.assertEqual(diagnostics.collect(1, ended=302)["capture_status"], "invalid_time_window")
            capture.assert_not_called()
            self.assertEqual(diagnostics.collect(100, ended=200)["capture_status"], "ok")
            command = capture.call_args.args[0]
            self.assertIn("@100", command)
            self.assertIn("@200", command)
            self.assertNotIn("--debug", command)

    def test_preflight_never_exports_prior_events(self):
        with patch.object(sys, "argv", ["diagnostics", "--check"]), patch.object(
            diagnostics, "collect", return_value={"capture_status": "ok", "records": ["private"]}
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(diagnostics.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {"capture_status": "ok", "decryption_proven": False})

if __name__ == "__main__":
    unittest.main()
