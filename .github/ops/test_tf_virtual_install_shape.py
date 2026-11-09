import json
from pathlib import Path
import tempfile
import unittest
from tf_virtual_beta_download import response_shape

class InstallShapeTests(unittest.TestCase):
    def test_private_values_and_unknown_keys_never_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"response.json"
            path.write_text(json.dumps({"data":{"url":"PRIVATE_URL","dpInfo":"PRIVATE_KEY",
                "UNKNOWN_PRIVATE_KEY":"PRIVATE_VALUE","assets":[{"url":"PRIVATE_URL_2"}]},
                "status":200,"error":None}))
            value=response_shape(path);encoded=json.dumps(value)
            self.assertNotIn("PRIVATE",encoded)
            self.assertTrue(value["parsed"])
            self.assertEqual(value["nodes"][1]["fields"]["url"],"string_nonempty")
            self.assertEqual(value["nodes"][1]["other_fields"],1)
    def test_invalid_json_and_missing_are_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"response.json"
            self.assertEqual(response_shape(path),{"present":False})
            path.write_text("PRIVATE_BAD_JSON")
            self.assertEqual(response_shape(path),{"present":True,"parsed":False})
