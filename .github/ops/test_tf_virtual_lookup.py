import unittest
from tf_virtual_lookup import header_lines

class LookupPrivacyTests(unittest.TestCase):
    def test_machine_only_headers_are_allowed(self):
        self.assertEqual(header_lines({"X-Apple-I-MD":"SYNTHETIC","User-Agent":"Synthetic"}).count("\n"),2)

    def test_account_headers_and_line_injection_are_rejected(self):
        for headers in ({"Cookie":"PRIVATE"},{"Authorization":"PRIVATE"},{"X-DSID":"1234"},
                        {"User-Agent":"Synthetic\r\nCookie: PRIVATE"},{"bad\nname":"x"}):
            with self.subTest(headers=list(headers)),self.assertRaises(ValueError):header_lines(headers)

    def test_header_values_must_have_closed_types_and_size(self):
        for headers in ({"X-Apple-I-MD":True},{"X-Apple-I-MD":"x"*16385},{}):
            with self.assertRaises(ValueError):header_lines(headers)
