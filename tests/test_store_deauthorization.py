import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import store_account_summary as account
import store_deauthorization as manage
from test_store_account_summary import session, response, Reply, Transport


class ManageTests(unittest.TestCase):
    def run_with(self, replies, confirmation=manage.CONFIRMATION):
        transport = Transport(replies)
        result = manage.operate(session(), confirmation, transport)
        mutations = [r for r in transport.requests if r.full_url == manage.ENDPOINT]
        self.assertLessEqual(len(mutations), 1)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))
        return result, transport

    def test_preview_never_performs_io(self):
        with patch.object(account, "fetch_summary") as query, patch.object(account, "run_private") as login:
            result = manage.preview()
        query.assert_not_called()
        login.assert_not_called()
        self.assertFalse(result["network_request_attempted"])
        self.assertFalse(result["mutation_request_attempted"])
        self.assertTrue(result["affects_all_computer_purchase_authorizations"])

    def test_explicit_confirmation_is_required_before_any_request(self):
        for value in ("", None, True, "yes", "continue", manage.CONFIRMATION + " "):
            with self.subTest(value=value):
                result, transport = self.run_with([], value)
                self.assertEqual(result["status"], "explicit_confirmation_required")
                self.assertEqual(transport.requests, [])

    def test_request_builder_also_requires_confirmation(self):
        with self.assertRaises(ValueError):
            manage.mutation_request(session(), "")

    def test_mutation_request_matches_public_frontend_and_preserves_identity(self):
        request = manage.mutation_request(session(), manage.CONFIRMATION)
        self.assertEqual(request.full_url, "https://buy.itunes.apple.com/account/deauthAllMachines")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b"")
        self.assertEqual(request.get_header("X-dsid"), session()["dsid"])
        self.assertEqual(request.get_header("X-token"), session()["token"])
        self.assertEqual(request.get_header("User-agent"), session()["user_agent"])
        self.assertIn("application/json", request.get_header("Content-type"))

    def test_cookie_path_is_recomputed_for_mutation(self):
        private = session()
        private["cookies"] += [
            dict(name="summary_only", value="PRIVATE_SUMMARY", domain=".itunes.apple.com", path="/account/v1"),
            dict(name="deauth_only", value="PRIVATE_DEAUTH", domain=".itunes.apple.com", path="/account/deauthAllMachines")]
        request = manage.mutation_request(private, manage.CONFIRMATION)
        self.assertNotIn("PRIVATE_SUMMARY", request.get_header("Cookie"))
        self.assertIn("PRIVATE_DEAUTH", request.get_header("Cookie"))

    def test_precondition_requires_fresh_count_of_five(self):
        for count in range(5):
            result, transport = self.run_with([Reply(200, response(count))])
            self.assertEqual(result["status"], "precondition_count_changed")
            self.assertEqual(len(transport.requests), 1)
            self.assertFalse(result["mutation_request_attempted"])

    def test_precondition_http_error_never_mutates(self):
        result, transport = self.run_with([Reply(401, response(5))])
        self.assertEqual(result["status"], "precondition_count_unavailable")
        self.assertEqual(len(transport.requests), 1)

    def test_partial_precondition_data_never_mutates(self):
        result, transport = self.run_with([Reply(200, response(5, errors=[{"message":"PRIVATE_SYNTHETIC"}]))])
        self.assertEqual(result["status"], "precondition_count_unavailable")
        self.assertEqual(len(transport.requests), 1)

    def test_success_requires_fresh_postcondition_zero(self):
        result, transport = self.run_with([
            Reply(200, response(5)), Reply(200, b"PRIVATE_SYNTHETIC_BODY"), Reply(200, response(0))])
        self.assertEqual(result["status"], "deauthorization_confirmed")
        self.assertEqual((result["count_before"], result["count_after"]), (5, 0))
        self.assertEqual(result["mutation_request_count"], 1)
        self.assertEqual([r.full_url for r in transport.requests],
                         [account.ENDPOINT, manage.ENDPOINT, account.ENDPOINT])

    def test_http_200_with_unchanged_count_is_not_success(self):
        result, _ = self.run_with([Reply(200, response(5)), Reply(200, b"{}"), Reply(200, response(5))])
        self.assertEqual(result["status"], "deauthorization_not_confirmed")

    def test_mutation_redirect_is_not_replayed(self):
        result, transport = self.run_with([
            Reply(200, response(5)), Reply(307, headers={"Location":"https://p42-buy.itunes.apple.com/account/deauthAllMachines"}),
            Reply(200, response(5))])
        self.assertTrue(result["mutation_redirect_blocked"])
        self.assertEqual(result["mutation_request_count"], 1)
        self.assertEqual(len(transport.requests), 3)

    def test_unauthorized_mutation_with_zero_count_is_not_operation_success(self):
        result, _ = self.run_with([Reply(200, response(5)), Reply(403, b"{}"), Reply(200, response(0))])
        self.assertEqual(result["status"], "count_zero_after_unconfirmed_response")

    def test_oversized_response_is_not_operation_success(self):
        result, _ = self.run_with([
            Reply(200, response(5)), Reply(200, b"x"*(account.MAX_RESPONSE + 1)), Reply(200, response(0))])
        self.assertTrue(result["mutation_response_oversized"])
        self.assertEqual(result["status"], "count_zero_after_unconfirmed_response")

    def test_timeout_is_not_retried_and_state_is_rechecked(self):
        transport = Transport([Reply(200, response(5)), Reply(200, response(0))])
        original = transport.open
        def open_request(request, timeout):
            if request.full_url == manage.ENDPOINT:
                transport.requests.append(request)
                raise TimeoutError("PRIVATE_SYNTHETIC")
            return original(request, timeout)
        transport.open = open_request
        result = manage.operate(session(), manage.CONFIRMATION, transport)
        self.assertEqual(result["status"], "count_zero_after_unconfirmed_response")
        self.assertTrue(result["mutation_transport_failed"])
        self.assertEqual(len(transport.requests), 3)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_postcondition_errors_preserve_attempt_state(self):
        result, _ = self.run_with([
            Reply(200, response(5)), Reply(200, b"{}"), Reply(200, response(0, errors=["PRIVATE_SYNTHETIC"]))])
        self.assertEqual(result["status"], "postcondition_count_unavailable")
        self.assertTrue(result["mutation_request_attempted"])
        self.assertEqual(result["mutation_request_count"], 1)

    def test_unexpected_postcondition_exception_preserves_attempt_state(self):
        before = dict(account.base_report(True), status="computer_count_observed",
                      computer_count_observed=True, http_status=200, authorized_computers=5)
        with patch.object(account, "fetch_summary", side_effect=[before, ValueError("PRIVATE_SYNTHETIC")]):
            result, _ = self.run_with([Reply(200, b"{}")])
        self.assertEqual(result["status"], "postcondition_count_unavailable")
        self.assertTrue(result["mutation_request_attempted"])
        self.assertEqual(result["mutation_request_count"], 1)

    def test_confirmation_is_checked_before_login(self):
        with patch.object(account, "run_private") as login:
            result = manage.trial("/synthetic/login", "continue")
        login.assert_not_called()
        self.assertEqual(result["status"], "explicit_confirmation_required")

    def test_ambiguous_login_is_redacted_and_never_mutates(self):
        with patch.dict(os.environ, {"APPLE_ID":"reader@example.invalid","APPLE_PASSWORD":"PRIVATE_SYNTHETIC"}), \
                patch.object(account, "run_private", return_value=(1, b"PRIVATE_SYNTHETIC", b"apple_auth_ambiguous_bad_login")), \
                patch.object(manage, "operate") as operation:
            result = manage.trial("/synthetic/login", manage.CONFIRMATION)
        operation.assert_not_called()
        self.assertEqual(result["status"], "login_ambiguous")
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
