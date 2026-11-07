import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, call
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_store import authenticate, classify
from private_export import export, main, ExportError
from telegram_queue import GitHub
from task_progress import ProgressCard

def response(code=1, error="authentication failed: HTTP 503"):
    return subprocess.CompletedProcess([], code, "", error)

class AuthenticationRetryTests(unittest.TestCase):
    def test_503_then_success_reuses_arguments_and_is_bounded(self):
        execute = Mock(side_effect=[response(), response(0, "")])
        retry = Mock()
        output = io.StringIO()
        with patch("native_store.time.sleep") as sleep, contextlib.redirect_stdout(output):
            result = authenticate("tool", ["login", "private@example.invalid"],
                                  {"APPLEPACKAGE_PASSWORD": "PRIVATE_PASSWORD"},
                                  execute=execute, on_retry=retry)
        self.assertEqual(classify(result), "authenticated")
        self.assertEqual(execute.call_count, 2)
        sleep.assert_called_once_with(5)
        retry.assert_called_once_with()
        self.assertEqual(execute.call_args_list[0], execute.call_args_list[1])
        self.assertEqual(execute.call_args.kwargs["timeout"], 45)
        self.assertNotIn("PRIVATE_PASSWORD", output.getvalue())
        self.assertNotIn("private@example.invalid", output.getvalue())
        self.assertEqual(json.loads(output.getvalue().splitlines()[0])["http_statuses"], [503])

    def test_persistent_service_failure_stops_after_three_attempts(self):
        execute = Mock(return_value=response())
        with patch("native_store.time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            result = authenticate("tool", ["login", "synthetic"], {}, execute=execute)
        self.assertEqual(classify(result), "native_auth_service_unavailable")
        self.assertEqual(execute.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(5), call(10)])

    def test_account_challenges_and_unknown_errors_are_not_retried(self):
        for error in ("apple_auth_ambiguous_bad_login", "verification code required",
                      "invalid or expired 2FA code (failureType: 5005)",
                      "HTTP 401", "HTTP 403", "HTTP 429", "unknown PRIVATE_RESPONSE",
                      "SAP certificate failure"):
            execute = Mock(return_value=response(error=error))
            output = io.StringIO()
            with patch("native_store.time.sleep") as sleep, contextlib.redirect_stdout(output):
                authenticate("tool", ["login", "synthetic"], {}, execute=execute)
            execute.assert_called_once()
            sleep.assert_not_called()
            self.assertNotIn("PRIVATE_RESPONSE", output.getvalue())

    def test_timeout_is_bounded_and_does_not_expose_exception(self):
        execute = Mock(side_effect=subprocess.TimeoutExpired(["SECRET_COMMAND"], 45, output="SECRET"))
        out = io.StringIO()
        with patch("native_store.time.sleep"), contextlib.redirect_stdout(out):
            result = authenticate("tool", ["login", "synthetic"], {}, execute=execute)
        self.assertEqual(execute.call_count, 3)
        self.assertEqual(classify(result), "native_auth_transport_failed")
        self.assertNotIn("SECRET", out.getvalue())

    def test_success_and_http_permanent_rejection_precede_transport_text(self):
        self.assertEqual(classify(response(0, "HTTP 503")), "authenticated")
        self.assertNotEqual(classify(response(error="HTTP 403 remoteConnectionClosed")),
                            "native_auth_transport_failed")
        self.assertEqual(classify(response(error="Error: remoteConnectionClosed")),
                         "native_auth_transport_failed")

    def test_export_stops_before_download_and_cleans_login(self):
        calls = []
        def execute(binary, args, env, **kwargs):
            calls.append(args[0])
            return response() if args[0] == "login" else response(0, "")
        progress = Mock()
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(os.environ, {"GITHUB_ACTIONS":"true", "APPLE_ID":"synthetic",
                                     "APPLE_PASSWORD":"synthetic", "DELIVERY_VERSION":""}), \
             patch("private_export.readiness", return_value=[]), \
             patch("private_export.metadata", return_value={"bundleId":"test.app"}), \
             patch("private_export.check_capacity"), \
             patch("private_export.run", side_effect=execute), \
             patch("native_store.time.sleep"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ExportError, "^native_auth_service_unavailable$"):
                export("tool","engine","crypt","333903271","a"*32,"age1"+"a"*58,
                       Path(directory)/"output",progress)
        self.assertEqual(calls, ["login", "login", "login", "logout"])
        self.assertEqual(progress.call_args_list, [call("metadata"),call("authenticating"),
                                                  call("auth_retry"),call("auth_retry")])

    def test_service_failure_exposes_only_fixed_workflow_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"outputs"
            with patch.dict(os.environ, {"GITHUB_ACTIONS":"true","GITHUB_OUTPUT":str(output)}), \
                 patch("sys.argv", ["export","--binary","x","--engine","y","--crypt","z"]), \
                 patch("private_export.Path.read_text",return_value='{"recipient":"synthetic"}'), \
                 patch("private_export.WorkerProgress"), patch("private_export.os.umask"), \
                 patch("private_export.export",side_effect=ExportError("native_auth_service_unavailable")), \
                 patch("shutil.rmtree"), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(),2)
            self.assertEqual(output.read_text(), "authentication_failure=temporary_unavailable\n")

    def test_access_denied_is_explicit_and_does_not_retry(self):
        self.assertEqual(classify(response(error="HTTP 403")), "native_auth_access_denied")
        github = GitHub("synthetic")
        github.jobs = Mock(return_value=[{"steps":[{"name":"Apple login access denied",
                                                  "conclusion":"failure"}]}])
        self.assertIn("401/403", github.failure_reason({}))
        self.assertIn("不能单独证明密码错误", github.failure_reason({}))

    def test_bot_reports_exhausted_retry_and_waiting_stage(self):
        github = GitHub("synthetic")
        github.jobs = Mock(return_value=[{"steps":[{"name":"Apple login temporarily unavailable",
                                                  "conclusion":"failure"}]}])
        self.assertIn("3 次", github.failure_reason({}))
        self.assertIn("等待重试", ProgressCard(Mock(),123,"a"*32).render("auth_retry"))

if __name__ == "__main__":
    unittest.main()
