import base64
import copy
import json
import unittest
from unittest.mock import patch
from cn_arm_policy import snapshot,validate_backup,allow_reference,CNReferenceError,reference_run
import test_cn_session
class CNARMReferenceBoundary(unittest.TestCase):
    def setUp(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp();self.env=fixture.env()
        checkpoint={'schema':'ipa-lab-private-fairplay-state-v1','hardware':base64.b64encode(bytes.fromhex(fixture.value['guid'])).decode(),'files':{'fpsd_sidb':base64.b64encode(b'SYNTHETIC_STATE').decode()}}
        self.env['FAIRPLAY_CN_STATE_B64']=base64.b64encode(json.dumps(checkpoint).encode()).decode()
        self.env.update(GITHUB_ACTIONS='true',GITHUB_REPOSITORY='zwthys-cyber/ipa-decrypt-lab',GITHUB_WORKFLOW_REF='zwthys-cyber/ipa-decrypt-lab/.github/workflows/cn-arm-model-bootstrap.yml@refs/heads/main',GITHUB_REF='refs/heads/main',GITHUB_EVENT_NAME='workflow_dispatch',GITHUB_RUN_ATTEMPT='1',CN_REFERENCE_ACK='true',CN_REFERENCE_NONCE='b'*32,GITHUB_SHA='a'*40,CN_MODEL_STATE_PRESENT='true')
        self.env['CN_RECOVERY_BACKUP_B64']=base64.b64encode(json.dumps(snapshot(self.env)).encode()).decode()
        self.env['CN_ARM_REFERENCE_APPROVAL']=json.dumps({'schema':'cn-arm-reference-approval-v1','nonce':'b'*32,'commit':'a'*40,'expires':1100})
    def ready(self,env):
        with patch('cn_arm_policy.platform.system',return_value='Darwin'),patch('cn_arm_policy.platform.machine',return_value='arm64'),patch('cn_arm_policy.platform.mac_ver',return_value=('15.7.2',(),'')),patch('cn_arm_policy.reference_run'):
            allow_reference(env,now=1000)
    def test_one_source_nonce_and_preserved_profile_can_pass(self):self.ready(self.env)
    def test_no_approval_rerun_other_workflow_or_wrong_nonce_can_authorize(self):
        for key,bad in [('CN_REFERENCE_ACK','false'),('CN_ARM_REFERENCE_APPROVAL','{}'),('CN_REFERENCE_NONCE','c'*32),('GITHUB_SHA','c'*40),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_WORKFLOW_REF','other/workflow@refs/heads/main'),('CN_MODEL_STATE_PRESENT','false')]:
            env=dict(self.env);env[key]=bad
            with self.assertRaises(Exception):self.ready(env)
    def test_expiry_and_wrong_platform_stop_before_native_authentication(self):
        env=dict(self.env);approval=json.loads(env['CN_ARM_REFERENCE_APPROVAL']);approval['expires']=999;env['CN_ARM_REFERENCE_APPROVAL']=json.dumps(approval)
        with self.assertRaises(Exception):self.ready(env)
        with patch('cn_arm_policy.platform.system',return_value='Darwin'),patch('cn_arm_policy.platform.machine',return_value='x86_64'):
            with self.assertRaises(Exception):allow_reference(self.env,now=1000)
    def test_changed_session_or_state_cannot_reuse_a_stale_backup(self):
        value=validate_backup(self.env);self.assertEqual(value['schema'],'cn-arm-prior-profile-v1')
        env=dict(self.env);backup=copy.deepcopy(value);backup['state_b64']=base64.b64encode(b'PRIVATE_OTHER_STATE').decode();env['CN_RECOVERY_BACKUP_B64']=base64.b64encode(json.dumps(backup).encode()).decode()
        with self.assertRaises(Exception):validate_backup(env)

class CNStandardTrialStaysClosed(unittest.TestCase):
    def test_saved_checkpoint_or_missing_reference_approval_never_reaches_authentication(self):
        from pathlib import Path
        from cn_model import trial,base
        with patch('cn_model.decode') as decode,patch('cn_model.live') as live:
            for reference in (False,True):
                with self.assertRaises(Exception):trial(Path('/public'),{'CN_MODEL_STATE_PRESENT':'true'},'trial',base(),reference_enrollment=reference)
            decode.assert_not_called();live.assert_not_called()

class CNReferenceIntentDeduplication(unittest.TestCase):
    def record(self):return {'id':12,'path':'.github/workflows/cn-arm-model-bootstrap.yml','head_branch':'main','event':'workflow_dispatch','status':'in_progress','head_sha':'a'*40,'display_title':'CN-arm-model-trial-'+'b'*32,'run_attempt':1}
    def env(self):return {'GITHUB_RUN_ID':'12','CN_REFERENCE_NONCE':'b'*32,'GITHUB_SHA':'a'*40,'GH_TOKEN':'PRIVATE_SYNTHETIC_TOKEN'}
    def test_only_one_bound_approval_intent_can_proceed(self):
        with patch('cn_arm_policy.GitHub') as github:
            github.return_value.call.side_effect=[self.record(),{'workflow_runs':[self.record()]}]
            reference_run(self.env())
            for status in ('queued','in_progress','completed'):
                prior=dict(self.record(),id=11,status=status,conclusion='failure')
                github.return_value.call.side_effect=[self.record(),{'workflow_runs':[self.record(),prior]}]
                with self.assertRaises(Exception):reference_run(self.env())
    def test_wrong_source_retries_and_truncated_history_cannot_reopen_an_intent(self):
        with patch('cn_arm_policy.GitHub') as github:
            for change in ({'head_sha':'c'*40},{'run_attempt':2},{'display_title':'CN-arm-model-trial'}):
                github.return_value.call.side_effect=[dict(self.record(),**change)]
                with self.assertRaises(Exception):reference_run(self.env())
            github.return_value.call.side_effect=[self.record(),{'workflow_runs':[self.record()]*100}]
            with self.assertRaises(Exception):reference_run(self.env())
