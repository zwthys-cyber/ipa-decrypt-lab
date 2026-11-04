import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("authorization_code",
    Path(__file__).parents[1] / "tools/native_authorization_code.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class AuthorizationCodeContracts(unittest.TestCase):
    def test_process_output_and_unapproved_functions_are_not_published(self):
        sample = "\n".join([
            "SECRET process/environment output",
            "AppleMediaServices\x60-[AMSAuthorizeMachineTask _buildRequestParametersWithError:]:",
            "  0x1000 <+0>: bl 0x2000 ; objc_msgSend$ams_secureToken",
            "  0x1004 <+4>: mov x1, x0",
            "(lldb) process kill",
            "  0x2000 <+0>: SECRET",
            "OtherModule\x60-[AMSAuthorizeMachineTask _buildRequest]:",
            "  0x1000 <+0>: SECRET",
            "AppleMediaServices\x60-[OtherClass unrelated]:",
            "  0x1000 <+0>: SECRET",
        ])
        value = mod.extract(sample)
        self.assertNotIn("SECRET", json.dumps(value))
        self.assertEqual(value[mod.METHODS[0]]["instruction_count"], 2)
        self.assertEqual(value[mod.METHODS[0]]["field_context"][0]["offset"], 0)

    def test_commerce_methods_require_their_exact_module(self):
        for name in mod.COMMERCE_SYMBOLS:
            with self.subTest(symbol=name):
                good = mod.extract("CommerceKit\x60" + name + ":\n  0x1000 <+0>: bl 0x2000 ; kbSyncForTransactionType")
                self.assertIn(name, good)
                for module in ("OtherModule", "AppleMediaServices"):
                    self.assertEqual(mod.extract(module + "\x60" + name + ":\n  0x1000 <+0>: PRIVATE"), {})
        self.assertEqual(mod.extract("CommerceKit\x60" + mod.METHODS[0] + ":\n  0x1000 <+0>: PRIVATE"), {})

    def test_bad_or_oversized_output_is_rejected(self):
        for value in (None, [], "x" * 524289):
            self.assertEqual(mod.extract(value), {})

    def test_only_bounded_instruction_lines_are_included(self):
        sample = "\n".join([
            "AppleMediaServices\x60-[AMSAuthorizeMachineTask _buildRequest]:",
            "  0x1000 <+0>: bl 0x2000 ; setAnisetteType",
            "  0x1004 <+4>: " + "SECRET" * 300,
            "  0x1008 <+99999>: SECRET",
        ])
        value = mod.extract(sample)
        self.assertNotIn("SECRET", json.dumps(value))
        self.assertEqual(value[mod.METHODS[1]]["instruction_count"], 1)

    def test_category_names_are_normalized_only_for_allowed_methods(self):
        sample = "\n".join([
            "AppleMediaServices\x60-[NSDictionary(AppleMediaServices) ams_secureToken]:",
            "  0x1000 <+0>: bl 0x2000 ; objectForKey:",
            "AppleMediaServices\x60-[NSDictionary(UnknownCategory) unrelated]:",
            "  0x1000 <+0>: SECRET",
        ])
        value = mod.extract(sample)
        self.assertEqual(value["-[NSDictionary ams_secureToken]"]["instruction_count"], 1)
        self.assertNotIn("SECRET", json.dumps(value))
