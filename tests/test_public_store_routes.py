import json
from pathlib import Path
import plistlib
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import public_store_routes as routes

class PublicRoutesTests(unittest.TestCase):
    def test_wrapped_and_nested_bags(self):
        payload = plistlib.dumps({"urlBag": {"accountSummary": "itmss://buy.itunes.apple.com/WebObjects/MZFinance.woa/wa/accountSummary"}})
        wrapped = b"<Document><Protocol>" + payload + b"</Protocol></Document>"
        value = routes.inspect(routes.decode(wrapped))
        self.assertEqual(value["routes"][0]["key"], "accountSummary")
        nested = routes.inspect({"bag": plistlib.dumps(routes.decode(wrapped))})
        self.assertEqual(nested["routes"], value["routes"])

    def test_query_values_and_non_route_private_fields_never_export(self):
        result = routes.inspect({"urlBag": {
            "accountSummary": "https://buy.itunes.apple.com/summary?token=PRIVATE&guid=PRIVATE",
            "privateAccountValue": "private@example.invalid",
        }})
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertNotIn("example.invalid", json.dumps(result))
        self.assertEqual(result["routes"][0]["query_keys"], ["guid", "token"])

    def test_external_or_userinfo_routes_rejected(self):
        for url in ("https://apple.com.evil.invalid/path", "https://secret@buy.itunes.apple.com/path",
                    "file:///private", "https://buy.itunes.apple.com:444/path"):
            self.assertIsNone(routes.route(url))

    def test_deep_and_oversized_inputs_fail_bounded(self):
        with self.assertRaises(ValueError):
            routes.decode(b"x" * (routes.MAX_BYTES + 1))
        nested = {"accountSummary": "https://buy.itunes.apple.com/path"}
        for _ in range(12):
            nested = {"nested": nested}
        self.assertEqual(routes.inspect(nested)["routes"], [])

if __name__ == "__main__":
    unittest.main()
