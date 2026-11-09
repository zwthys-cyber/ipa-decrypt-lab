import sqlite3
import tempfile
from pathlib import Path
import unittest
from tf_invitation import invite_code, request_plan, response_category, InvitationJournal

class InvitationTests(unittest.TestCase):
    def test_canonical_link_and_account_bound_requests(self):
        code=invite_code("https://testflight.apple.com/join/yoNuHexZ")
        lookup=request_plan("synthetic-account",code)
        accept=request_plan("synthetic-account",code,accept=True)
        self.assertEqual(lookup.method,"GET")
        self.assertEqual(accept.method,"POST")
        self.assertEqual(accept.url,lookup.url+"/accept")

    def test_untrusted_link_cannot_choose_origin_or_inject_path(self):
        for link in (
            "http://testflight.apple.com/join/yoNuHexZ",
            "https://testflight.apple.com.evil.invalid/join/yoNuHexZ",
            "https://testflight.apple.com@evil.invalid/join/yoNuHexZ",
            "https://testflight.apple.com:443/join/yoNuHexZ",
            "https://testflight.apple.com/join/yoNuHexZ?next=evil",
            "https://testflight.apple.com/join/yoNuHexZ#fragment",
            "https://testflight.apple.com/join/%79oNuHexZ",
            "https://testflight.apple.com/join/yoNuHexZ\n"):
            with self.subTest(link=link),self.assertRaises(ValueError):
                invite_code(link)
        with self.assertRaises(ValueError):request_plan("../other","yoNuHexZ")

    def test_success_status_never_claims_accepted(self):
        for status in (200,201,204):
            self.assertEqual(response_category(status),"response_requires_verification")
        self.assertEqual(response_category(403),"authentication_required")
        self.assertEqual(response_category(429),"rate_limited")

    def test_crash_after_intent_blocks_repeat_across_connections_and_jobs(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"private-synthetic.db"
            with sqlite3.connect(path) as first:
                self.assertTrue(InvitationJournal(first).claim("synthetic-account","yoNuHexZ","job-1"))
            with sqlite3.connect(path) as resumed:
                journal=InvitationJournal(resumed)
                self.assertFalse(journal.claim("synthetic-account","yoNuHexZ","job-2"))
                self.assertTrue(journal.claim("another-account","yoNuHexZ","job-3"))
                rows=resumed.execute("SELECT account_binding,state FROM tf_invitation_intents").fetchall()
                self.assertTrue(all(len(account)==64 for account,state in rows))
                self.assertTrue(all(state=="acceptance_outcome_unverified" for account,state in rows))
