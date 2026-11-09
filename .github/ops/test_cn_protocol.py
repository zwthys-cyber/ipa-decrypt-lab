import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
import cn_protocol as p
from cn_live_auth import live
from telegram_queue import QueueError
class LiveProtocolContracts(unittest.TestCase):
    def waiting(self):return {'schema':'cn-live-request-v1','auth_run':'12','commit':'a'*40,'nonce':'b'*32,'expires':int(time.time())+100}
    def payload(self,w):return dict(schema='cn-live-code-v1',auth_run=w['auth_run'],commit=w['commit'],nonce=w['nonce'],issued_at=int(time.time()),code='123456')
    def test_nonce_source_expiry_and_code_shape_are_bound(self):
        w=self.waiting();value=self.payload(w);self.assertEqual(p.code_payload(value,w),'123456')
        for key,bad in [('nonce','c'*32),('commit','c'*40),('auth_run','13'),('issued_at',0),('code','１２３４５６')]:
            v=dict(value,**{key:bad})
            with self.assertRaises(Exception):p.code_payload(v,w)
        with self.assertRaises(Exception):p.request(dict(w,password='PRIVATE'),'12','a'*40)
    def test_untrusted_session_does_not_receive_code_or_network_path(self):
        api=Mock()
        with self.assertRaises(Exception):p.waiting_request(api,'../secrets','b'*32,'a'*40)
        api.call.assert_not_called()
        api.call.return_value={'path':p.AUTH,'head_branch':'main','event':'workflow_dispatch','display_title':'China-account-authenticate','status':'completed','head_sha':'a'*40}
        with self.assertRaises(Exception):p.waiting_request(api,'12','b'*32,'a'*40)
    def test_only_active_trusted_model_trials_receive_live_code(self):
        waiting=self.waiting()
        for title in ('CN-model-trial','CN-model-replay','CN-model-preflight','untrusted'):
            api=Mock()
            run={'path':'.github/workflows/china-model-bootstrap.yml','head_branch':'main','event':'workflow_dispatch','display_title':title,'status':'in_progress','head_sha':'a'*40}
            api.call.side_effect=[run,{'artifacts':[{'name':'cn-auth-request-12-'+'b'*32}]}]
            with patch.object(p,'artifact_bytes',return_value=json.dumps(waiting).encode()):
                if title in ('CN-model-trial','CN-model-replay'):
                    self.assertEqual(p.waiting_request(api,'12','b'*32,'a'*40),waiting)
                else:
                    with self.assertRaises(Exception):p.waiting_request(api,'12','b'*32,'a'*40)
                    self.assertEqual(api.call.call_count,1)
    def test_arm_reference_preparation_cannot_receive_codes(self):
        waiting=self.waiting()
        for title in ('CN-arm-model-trial-'+'c'*32,'CN-arm-model-replay','CN-arm-model-trial','CN-arm-model-preflight','CN-arm-model-backup'):
            api=Mock();api.call.side_effect=[{'path':'.github/workflows/cn-arm-model-bootstrap.yml','head_branch':'main','event':'workflow_dispatch','display_title':title,'status':'in_progress','head_sha':'a'*40},{'artifacts':[{'name':'cn-auth-request-12-'+'b'*32}]}]
            with patch.object(p,'artifact_bytes',return_value=json.dumps(waiting).encode()):
                if title in ('CN-arm-model-trial-'+'c'*32,'CN-arm-model-replay'):self.assertEqual(p.waiting_request(api,'12','b'*32,'a'*40),waiting)
                else:
                    with self.assertRaises(Exception):p.waiting_request(api,'12','b'*32,'a'*40)
                    self.assertEqual(api.call.call_count,1)
    def test_only_active_saved_model_verification_can_receive_live_code(self):
        waiting=self.waiting()
        for title in ('CN-saved-model-verify','CN-saved-model-preflight'):
            api=Mock();api.call.side_effect=[{'path':'.github/workflows/china-saved-model-check.yml','head_branch':'main','event':'workflow_dispatch','display_title':title,'status':'in_progress','head_sha':'a'*40},{'artifacts':[{'name':'cn-auth-request-12-'+'b'*32}]}]
            with patch.object(p,'artifact_bytes',return_value=json.dumps(waiting).encode()):
                if title=='CN-saved-model-verify':self.assertEqual(p.waiting_request(api,'12','b'*32,'a'*40),waiting)
                else:
                    with self.assertRaises(Exception):p.waiting_request(api,'12','b'*32,'a'*40)
    def test_artifact_digest_and_inventory_must_match(self):
        api=Mock();out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('request.json',json.dumps(self.waiting()))
        raw=out.getvalue();item={'id':1,'expired':False,'size_in_bytes':len(raw),'digest':'sha256:'+hashlib.sha256(raw).hexdigest()}
        api.archive.side_effect=lambda ident,path,**kwargs:path.write_bytes(raw)
        self.assertIsInstance(p.artifact_bytes(api,item,'request.json'),bytes)
        with self.assertRaises(Exception):p.artifact_bytes(api,dict(item,digest='sha256:'+'0'*64),'request.json')
        with self.assertRaises(Exception):p.artifact_bytes(api,item,'code.age')
    def test_decryption_uses_private_identity_without_native_account_secrets(self):
        w=self.waiting();value=self.payload(w);paths=[]
        def decrypt(args,**kwargs):
            self.assertEqual(kwargs['env']['DELIVERY_AGE_IDENTITY'],'PRIVATE_IDENTITY')
            self.assertNotIn('APPLE_CN_PASSWORD',kwargs['env'])
            target=Path(args[3]);target.write_text(json.dumps(value));target.chmod(0o600);paths.append(target)
            return Mock(returncode=0)
        self.assertEqual(p.decrypt_code('crypt',b'synthetic ciphertext',w,'PRIVATE_IDENTITY',execute=decrypt),'123456')
        self.assertTrue(all(not x.exists() for x in paths))
    def test_transient_github_read_keeps_the_same_waiting_child_alive(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);email='cn@example.invalid'
            env={'GITHUB_ACTIONS':'true','HOME':directory,'PATH':os.environ['PATH'],'APPLE_CN_ID':email,'APPLE_CN_PASSWORD':'PRIVATE_PASSWORD',
                'LEGACY_APPLE_ID':'legacy@example.invalid','APPLE_CN_GUID':'02123456789A','GITHUB_RUN_ID':'12','GITHUB_SHA':'a'*40,'CN_HANDSHAKE_FILE':str(root/'request.json')}
            program="""import os,json,hashlib;from pathlib import Path
print('IPA_CN_AUTH:verification_pending',flush=True)
assert input()=='123456'
p=Path(os.environ['HOME'])/'.ipatool'/hashlib.md5(b'cn@example.invalid').hexdigest();p.mkdir(parents=True)
f=p/'account.json';f.write_text(json.dumps({'email':'cn@example.invalid','store':'143465','passwordToken':'PRIVATE_TOKEN','directoryServicesIdentifier':'123'}));f.chmod(0o600)
"""
            calls=[]
            def relay(waiting):
                calls.append(waiting['nonce'])
                if len(calls)==1:raise QueueError('github_transport_unknown')
                return '123456'
            capture=io.StringIO()
            with contextlib.redirect_stdout(capture):
                result,_=live('/tool','/crypt',env,command=[sys.executable,'-c',program],relay=relay,window=5,poll_interval=.01)
            self.assertTrue(result['authenticated']);self.assertEqual(len(calls),2);self.assertEqual(calls[0],calls[1])
            self.assertIn('relay_read_retry',capture.getvalue());self.assertNotIn('PRIVATE',capture.getvalue())
    def test_same_child_waits_then_receives_code_without_leaking_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);handshake=root/'request.json';email='cn@example.invalid'
            env={'GITHUB_ACTIONS':'true','HOME':directory,'PATH':os.environ['PATH'],'APPLE_CN_ID':email,'APPLE_CN_PASSWORD':'PRIVATE_PASSWORD',
                 'LEGACY_APPLE_ID':'legacy@example.invalid','APPLE_CN_GUID':'02123456789A','GITHUB_RUN_ID':'12','GITHUB_SHA':'a'*40,'CN_HANDSHAKE_FILE':str(handshake)}
            program="""import os,json,hashlib;from pathlib import Path
print('PRIVATE_NATIVE_OUTPUT',flush=True)
print('IPA_CN_AUTH:verification_pending',flush=True)
assert input()=='123456'
p=Path(os.environ['HOME'])/'.ipatool'/hashlib.md5(b'cn@example.invalid').hexdigest();p.mkdir(parents=True)
f=p/'account.json';f.write_text(json.dumps({'email':'cn@example.invalid','store':'143465','passwordToken':'PRIVATE_SESSION','directoryServicesIdentifier':'123'}));f.chmod(0o600)
print('IPA_CN_AUTH:authenticated',flush=True)
"""
            requests=[]
            def relay(w):
                self.assertTrue(handshake.is_file());requests.append(w)
                return '123456'
            with contextlib.redirect_stdout(io.StringIO()) as output:
                result,envelope=live('binary','crypt',env,relay=relay,command=[sys.executable,'-u','-c',program],window=5,poll_interval=0.01)
            self.assertTrue(result['authenticated']);self.assertTrue(result['verification_submitted']);self.assertEqual(len(requests),1)
            self.assertEqual(envelope['store'],'143465')
            self.assertFalse((root/'.ipatool'/hashlib.md5(email.encode()).hexdigest()).exists())
            for secret in ('PRIVATE_NATIVE_OUTPUT','PRIVATE_PASSWORD','PRIVATE_SESSION','123456',email):self.assertNotIn(secret,output.getvalue())
    def test_wait_expiry_terminates_without_another_login(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            env={'GITHUB_ACTIONS':'true','HOME':directory,'PATH':os.environ['PATH'],'APPLE_CN_ID':'cn@example.invalid','APPLE_CN_PASSWORD':'PRIVATE',
                 'LEGACY_APPLE_ID':'legacy@example.invalid','APPLE_CN_GUID':'02123456789A','GITHUB_RUN_ID':'12','GITHUB_SHA':'a'*40,'CN_HANDSHAKE_FILE':str(root/'request.json')}
            program="print('IPA_CN_AUTH:verification_pending',flush=True);input()"
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(Exception,'verification_window_expired'):
                    live('binary','crypt',env,relay=lambda w:None,command=[sys.executable,'-u','-c',program],window=1,poll_interval=0.01)
if __name__=='__main__':unittest.main()
