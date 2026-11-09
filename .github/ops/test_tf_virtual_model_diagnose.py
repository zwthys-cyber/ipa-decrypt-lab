import json
import unittest
from tf_virtual_beta_model_diagnose import closed
class ModelDiagnosticPrivacy(unittest.TestCase):
    def test_only_closed_booleans_and_counts_escape(self):
        private={"schema":"unfairplay-doctor-v1","checks":{"selector_match":False,"model_valid":True,"PRIVATE":"PRIVATE"},
            "sinf":[{"selector_id":"PRIVATE","path":"PRIVATE"}],"models":[{"selector_id":"PRIVATE"}],
            "errors":["PRIVATE"],"host":{"PRIVATE":"PRIVATE"},"compatible_model":"PRIVATE"}
        result=closed(private)
        self.assertEqual(result,{"selector_match":False,"model_valid":True,"sinf_count":1,"model_count":1,"error_count":1})
        self.assertNotIn("PRIVATE",json.dumps(result))
    def test_wrong_schema_and_nonbool_checks_are_rejected_or_dropped(self):
        with self.assertRaises(ValueError):closed({"schema":"other","checks":{}})
        result=closed({"schema":"unfairplay-doctor-v1","checks":{"selector_match":1}})
        self.assertNotIn("selector_match",result)
