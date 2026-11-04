import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import native_commerce_debug as mod

class CommerceStackContracts(unittest.TestCase):
    def test_only_approved_static_frame_fields_are_published(self):
        raw = "PRIVATE debugger output\n" + mod.PREFIX + json.dumps({"stop_reason": 6, "frames": [
            {"module": "CommerceKit", "function": "+[ServiceProxy initialize]", "offset": 4, "registers": "PRIVATE"},
            {"module": "PRIVATE", "function": "PRIVATE", "offset": 0},
            {"module": "Foundation", "function": "/PRIVATE/path", "offset": 0},
            {"module": "Foundation", "function": "valid", "offset": True}]})
        value = mod.extract(raw)
        self.assertEqual(value["frames"], [{"module": "CommerceKit", "function": "+[ServiceProxy initialize]", "offset": 4}])
        self.assertNotIn("PRIVATE", json.dumps(value))

    def test_malformed_and_oversized_reports_fail_closed(self):
        for raw in (None, [], "x" * 131073, mod.PREFIX + "not-json",
                    mod.PREFIX + json.dumps({"frames": [{}] * 25})):
            self.assertEqual(mod.extract(raw), {})
        self.assertEqual(mod.extract(mod.PREFIX + json.dumps({"frames": [], "stop_reason": True})), {"frames": []})

if __name__ == "__main__":
    unittest.main()
