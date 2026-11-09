import base64
import copy
import json
import struct
import unittest
from cn_saved_model import validated_profile
import test_cn_session
class CNSavedModelBindings(unittest.TestCase):
    def setUp(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp();self.env=fixture.env()
        self.state={'schema':'ipa-lab-private-fairplay-state-v1','hardware':base64.b64encode(bytes.fromhex(fixture.value['guid'])).decode(),'files':{'fpsd_sidb':base64.b64encode(b'SYNTHETIC_STATE_NOT_REAL').decode()}}
        self.env['FAIRPLAY_CN_STATE_B64']=base64.b64encode(json.dumps(self.state).encode()).decode()
        model=b'FPSENR2\x00'+struct.pack('<II',2,4184)+bytes(4184-16)
        self.env['FAIRPLAY_CN_MODEL_B64']=base64.b64encode(model).decode()
    def test_paired_profile_encoding_is_only_readiness_not_plaintext_proof(self):self.assertEqual(validated_profile(self.env)['store'],'143465')
    def test_foreign_credentials_bad_model_or_mismatched_checkpoint_rejected_before_login(self):
        for key,value in [('APPLE_ID','de@example.invalid'),('FAIRPLAY_MODEL_B64','PRIVATE_OTHER_MODEL'),('FAIRPLAY_CN_MODEL_B64','not-base64')]:
            env=dict(self.env);env[key]=value
            with self.assertRaises(Exception):validated_profile(env)
        state=copy.deepcopy(self.state);state['hardware']=base64.b64encode(bytes.fromhex('AABBCCDDEEFF')).decode()
        env=dict(self.env,FAIRPLAY_CN_STATE_B64=base64.b64encode(json.dumps(state).encode()).decode())
        with self.assertRaises(Exception):validated_profile(env)
