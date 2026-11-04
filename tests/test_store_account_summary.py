import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import store_account_summary as account


def session():
    return dict(dsid="123456789", guid="001122334455", token="PRIVATE_SYNTHETIC_TOKEN",
                user_agent="SyntheticConfigurator/1", storefront="143441-1",
                cookies=[dict(name="session", value="PRIVATE_SYNTHETIC_COOKIE",
                              domain=".itunes.apple.com", path="/", expiresAt=None)])


def response(count=3, **extra):
    return json.dumps(dict(data={"authorizations": {"authorizedComputers": count}}, **extra)).encode()


class Reply(io.BytesIO):
    def __init__(self, code, data=b"", headers=None):
        super().__init__(data)
        self.code, self.headers = code, headers or {}


class Transport:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []

    def open(self, request, timeout):
        self.requests.append(request)
        return self.replies.pop(0)


class AccountSummaryTests(unittest.TestCase):
    def test_minimal_read_query_excludes_other_account_information(self):
        request = account.make_request(account.ENDPOINT, session())
        self.assertEqual(request.method, "POST")
        self.assertEqual(json.loads(request.data), {
            "query": "query requestAccountSummary { authorizations { authorizedComputers } }"})
        self.assertEqual(request.get_header("X-dsid"), session()["dsid"])
        self.assertEqual(request.get_header("Icloud-dsid"), session()["dsid"])
        self.assertEqual(request.get_header("X-token"), session()["token"])
        self.assertEqual(request.get_header("User-agent"), session()["user_agent"])
        self.assertIn("PRIVATE_SYNTHETIC_COOKIE", request.get_header("Cookie"))

    def test_unapproved_routes_never_receive_session(self):
        for url in ("http://buy.itunes.apple.com/account/v1/summary/graphql",
                    "https://buy.itunes.apple.com:443/account/v1/summary/graphql",
                    "https://buy.itunes.apple.com@attacker.invalid/account/v1/summary/graphql",
                    "https://buy.itunes.apple.com.attacker.invalid/account/v1/summary/graphql",
                    "https://buy.itunes.apple.com/commerce/machine/authorize",
                    "https://buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/deauthorizeMachine",
                    account.ENDPOINT + "?query=mutation",
                    account.ENDPOINT + "#private",
                    "https://apps.mzstatic.com/account/v1/summary/graphql"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                account.make_request(url, session())

    def test_header_injection_is_rejected(self):
        for key in ("dsid", "token", "user_agent", "storefront"):
            private = session()
            private[key] = "private\r\nX-Unwanted: value"
            with self.subTest(key=key), self.assertRaises(ValueError):
                account.make_request(account.ENDPOINT, private)

    def test_cookie_domain_path_and_expiry_filtering(self):
        values = [
            dict(name="accepted", value="ok", domain=".apple.com", path="/account", expiresAt=200),
            dict(name="wrong_host", value="secret", domain="auth.itunes.apple.com", path="/"),
            dict(name="wrong_path", value="secret", domain=".apple.com", path="/accounts"),
            dict(name="expired", value="secret", domain=".apple.com", path="/", expiresAt=99),
            dict(name="nan", value="secret", domain=".apple.com", path="/", expiresAt=float("nan")),
            dict(name="injection", value="secret; forged=x", domain=".apple.com", path="/"),
        ]
        self.assertEqual(account.cookie_header(values, account.ENDPOINT, now=100), "accepted=ok")

    def test_cookie_size_bound_is_enforced(self):
        private = session()
        private["cookies"] = [dict(name=str(i), value="x"*8192, domain=".apple.com", path="/") for i in range(3)]
        with self.assertRaises(ValueError):
            account.make_request(account.ENDPOINT, private)

    def test_only_real_computer_integer_counts_are_accepted(self):
        for count in range(6):
            result = account.parse_response(response(count), 200, True)
            self.assertEqual(result["authorized_computers"], count)
            self.assertTrue(result["computer_count_observed"])
        for count in (True, False, "5", 5.0, -1, 6, None, {}, []):
            result = account.parse_response(response(count), 200, True)
            self.assertNotIn("authorized_computers", result)
            self.assertNotEqual(result["status"], "computer_count_observed")

    def test_device_count_is_never_computer_count(self):
        raw = json.dumps({"data":{"authorizations":{"linkedDevices":5}, "authorizedComputers":4}}).encode()
        self.assertEqual(account.parse_response(raw, 200, True)["status"], "computer_count_not_returned")

    def test_partial_data_with_graphql_errors_is_rejected_and_private_message_redacted(self):
        result = account.parse_response(response(5, errors=[{"message":"PRIVATE_SYNTHETIC_ACCOUNT"}]), 200, True)
        self.assertEqual(result["status"], "graphql_errors")
        self.assertNotIn("authorized_computers", result)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_count_on_failed_http_or_without_login_is_not_accepted(self):
        for status in (401, 403, 500):
            self.assertNotIn("authorized_computers", account.parse_response(response(), status, True))
        result = account.parse_response(response(), 200, False)
        self.assertEqual(result["status"], "unexpected_unauthenticated_count")
        self.assertNotIn("authorized_computers", result)

    def test_apple_failure_takes_precedence_over_count(self):
        result = account.parse_response(response(5, failureType="3002", message="PRIVATE_SYNTHETIC"), 200, True)
        self.assertEqual(result["apple_failure_code"], 3002)
        self.assertNotIn("authorized_computers", result)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_approved_redirect_preserves_post_and_rebuilds_host_scoped_cookies(self):
        private = session()
        private["cookies"].append(dict(name="buy_only", value="PRIVATE_BUY", domain="buy.itunes.apple.com", path="/"))
        transport = Transport([Reply(307, headers={"Location":"https://p42-buy.itunes.apple.com/account/v1/summary/graphql"}),
                               Reply(200, response(5))])
        result = account.fetch_summary(private, transport)
        self.assertEqual(result["authorized_computers"], 5)
        self.assertEqual(result["approved_redirect_count"], 1)
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(transport.requests[1].method, "POST")
        self.assertEqual(transport.requests[1].data, account.BODY)
        self.assertIn("PRIVATE_BUY", transport.requests[0].get_header("Cookie"))
        self.assertNotIn("PRIVATE_BUY", transport.requests[1].get_header("Cookie"))
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_unsafe_redirects_are_not_followed(self):
        for code, target in ((302, account.ENDPOINT),
                             (307, "https://attacker.invalid/"),
                             (308, "https://buy.itunes.apple.com/commerce/machine/authorize"),
                             (307, account.ENDPOINT + "?token=PRIVATE_SYNTHETIC")):
            transport = Transport([Reply(code, headers={"Location":target})])
            result = account.fetch_summary(session(), transport)
            self.assertEqual(result["status"], "redirect_blocked")
            self.assertEqual(len(transport.requests), 1)
            self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_second_redirect_is_blocked(self):
        target = "https://p42-buy.itunes.apple.com/account/v1/summary/graphql"
        transport = Transport([Reply(307, headers={"Location":target}),
                               Reply(307, headers={"Location":account.ENDPOINT})])
        self.assertEqual(account.fetch_summary(session(), transport)["status"], "redirect_blocked")
        self.assertEqual(len(transport.requests), 2)

    def test_response_size_is_bounded(self):
        transport = Transport([Reply(200, b"x"*(account.MAX_RESPONSE + 1))])
        self.assertEqual(account.fetch_summary(session(), transport)["status"], "response_oversized")

    def test_private_handoff_is_deleted_after_read(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"session.json"
            path.write_text(json.dumps(session()))
            path.chmod(0o600)
            self.assertEqual(account.read_handoff(path)["guid"], session()["guid"])
            self.assertFalse(path.exists())

    def test_readable_or_invalid_handoff_is_rejected_and_deleted(self):
        with tempfile.TemporaryDirectory() as root:
            for mode, contents in ((0o644, json.dumps(session())), (0o600, "INVALID_PRIVATE")):
                path = Path(root)/"session.json"
                path.write_text(contents)
                path.chmod(mode)
                with self.assertRaises(ValueError):
                    account.read_handoff(path)
                self.assertFalse(path.exists())

    def test_symlink_handoff_is_not_read(self):
        with tempfile.TemporaryDirectory() as root:
            source, link = Path(root)/"source", Path(root)/"link"
            source.write_text("PRIVATE_SYNTHETIC")
            link.symlink_to(source)
            with self.assertRaises(OSError):
                account.read_handoff(link)

    def test_query_login_does_not_request_machine_enrollment(self):
        def login(argv, env, timeout):
            self.assertEqual(argv, ["/synthetic/login", "login", "reader@example.invalid"])
            self.assertEqual(env["LAB_AUTHORIZATION_PURPOSE"], "signIn")
            self.assertEqual(env["APPLEPACKAGE_PASSWORD"], "PRIVATE_SYNTHETIC_PASSWORD")
            path = Path(env["LAB_ENROLLMENT_INPUT_PATH"])
            path.write_text(json.dumps(session()))
            path.chmod(0o600)
            return 0, b"PRIVATE_SYNTHETIC_STDOUT", b"PRIVATE_SYNTHETIC_STDERR"
        expected = dict(account.base_report(True), status="computer_count_observed",
                        computer_count_observed=True, authorized_computers=5)
        with patch.dict(os.environ, {"APPLE_ID":"reader@example.invalid",
                                     "APPLE_PASSWORD":"PRIVATE_SYNTHETIC_PASSWORD"}), \
                patch.object(account, "run_private", side_effect=login), \
                patch.object(account, "fetch_summary", return_value=expected) as fetch:
            result = account.trial("/synthetic/login")
        fetch.assert_called_once()
        self.assertEqual(result["authorized_computers"], 5)
        self.assertFalse(result["machine_authorization_attempted"])
        self.assertFalse(result["deauthorization_attempted"])
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_login_failure_does_not_query_or_expose_private_output(self):
        with patch.dict(os.environ, {"APPLE_ID":"reader@example.invalid","APPLE_PASSWORD":"PRIVATE_SYNTHETIC"}), \
                patch.object(account, "run_private", return_value=(1, b"PRIVATE_SYNTHETIC", b"apple_auth_ambiguous_bad_login")), \
                patch.object(account, "fetch_summary") as fetch:
            result = account.trial("/synthetic/login")
        self.assertEqual(result["status"], "login_ambiguous")
        fetch.assert_not_called()
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_credential_free_request_contains_no_account_headers(self):
        transport = Transport([Reply(401, b'{"errors":[{"message":"Unauthenticated"}]}')])
        result = account.fetch_summary(opener=transport)
        request = transport.requests[0]
        for name in ("X-dsid", "Icloud-dsid", "X-token", "Cookie", "X-apple-store-front"):
            self.assertFalse(request.has_header(name))
        self.assertFalse(result["store_session_authenticated"])
        self.assertEqual(result["status"], "graphql_errors")


if __name__ == "__main__":
    unittest.main()
