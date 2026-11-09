import json
import unittest
from cn_recovery_inspect import sanitized,BOOLS,COUNTS
class CNRecoveryPrivacy(unittest.TestCase):
    def fixture(self):return dict({k:False for k in BOOLS},**{k:0 for k in COUNTS},schema='cn-offline-recovery-inspection-v1',status='input_rejected',stage='load_inputs')
    def test_private_and_unknown_fields_rejected(self):
        value=self.fixture();self.assertEqual(sanitized(json.dumps(value).encode()),value)
        for k,v in [('selector','PRIVATE'),('hardware','PRIVATE'),('error','PRIVATE_PATH'),('model_written',True),('registry_count',True),('tree_nodes',1048577)]:
            candidate=dict(value);candidate[k]=v
            with self.assertRaises(ValueError):sanitized(json.dumps(candidate).encode())
    def test_inconsistent_proof_rejected(self):
        value=self.fixture();value['full_license_accepted']=True
        with self.assertRaises(ValueError):sanitized(json.dumps(value).encode())
