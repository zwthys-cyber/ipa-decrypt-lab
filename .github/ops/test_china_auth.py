import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('china_auth',Path(__file__).with_name('china_auth.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class ChinaAuthenticationContracts(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.env={'GITHUB_ACTIONS':'true','HOME':self.directory.name,'PATH':'synthetic',
                  'APPLE_CN_ID':'china@example.invalid','APPLE_CN_PASSWORD':'CN_PRIVATE_PASSWORD',
                  'LEGACY_APPLE_ID':'legacy@example.invalid','APPLE_CN_GUID':'02123456789A',
                  'APPLE_CN_2FA_CODE':'123456','APPLE_PASSWORD':'LEGACY_PRIVATE_PASSWORD',
                  'FAIRPLAY_MODEL_B64':'LEGACY_PRIVATE_MODEL','TELEGRAM_BOT_TOKEN':'PRIVATE_TOKEN'}
    def tearDown(self):self.directory.cleanup()
    def execute(self,binary,args,env,timeout,store='143465'):
        self.assertEqual(args,['login',self.env['APPLE_CN_ID'],'--guid',self.env['APPLE_CN_GUID'],'--code','123456'])
        self.assertEqual(env['APPLEPACKAGE_PASSWORD'],'CN_PRIVATE_PASSWORD')
        for field in ('APPLE_PASSWORD','FAIRPLAY_MODEL_B64','TELEGRAM_BOT_TOKEN','LEGACY_APPLE_ID'):self.assertNotIn(field,env)
        folder=Path(env['HOME'])/'.ipatool'/module.hashlib.md5(self.env['APPLE_CN_ID'].encode()).hexdigest()
        folder.mkdir(parents=True);path=folder/'account.json'
        path.write_text(json.dumps({'email':self.env['APPLE_CN_ID'],'passwordToken':'PRIVATE_SESSION','directoryServicesIdentifier':'123456','store':store}))
        path.chmod(0o600)
        return subprocess.CompletedProcess([],0,'login successful for PRIVATE_ACCOUNT','')
    def test_cn_binding_and_private_cache_cleanup(self):
        result=module.probe('binary',self.env,execute=self.execute)
        self.assertTrue(result['authenticated']);self.assertEqual(result['country_verified'],'cn')
        self.assertEqual(list((Path(self.directory.name)/'.ipatool').iterdir()),[])
        for value in ('CN_PRIVATE_PASSWORD','PRIVATE_SESSION','PRIVATE_ACCOUNT','LEGACY_PRIVATE_PASSWORD','123456'):self.assertNotIn(value,json.dumps(result))
    def test_old_account_is_rejected_before_native_execution(self):
        env=dict(self.env,APPLE_CN_ID=' LEGACY@example.invalid ')
        with self.assertRaisesRegex(module.ChinaAuthError,'same_account_not_allowed'):
            module.probe('binary',env,execute=lambda *a,**k:self.fail('legacy was touched'))
    def test_missing_credentials_and_malformed_code_fail_closed(self):
        for values in ({'APPLE_CN_PASSWORD':''},{'APPLE_CN_2FA_CODE':'00000'},{'APPLE_CN_GUID':''},{'GITHUB_ACTIONS':''}):
            with self.assertRaises(module.ChinaAuthError):module.settings(dict(self.env,**values))
    def test_wrong_country_is_not_relabelled_or_fallback_to_legacy(self):
        with self.assertRaisesRegex(module.ChinaAuthError,'china_storefront_mismatch'):
            module.probe('binary',self.env,execute=lambda *a,**k:self.execute(*a,**k,store='143443'))
        self.assertEqual(list((Path(self.directory.name)/'.ipatool').iterdir()),[])
    def test_challenge_and_ambiguous_bad_login_stop_without_retry(self):
        for text,expected in [('verification code required','native_verification_unresolved'),('APPLE_AUTH_AMBIGUOUS_BAD_LOGIN','native_generic_bad_login')]:
            calls=[]
            def fail(*args,**kwargs):calls.append(1);return subprocess.CompletedProcess([],2,text,'PRIVATE_ACCOUNT')
            result=module.probe('binary',self.env,execute=fail)
            self.assertEqual(result['status'],expected);self.assertEqual(len(calls),1);self.assertFalse(result['authenticated'])
    def test_otp_rejection_diagnostic_never_echoes_raw_output(self):
        result=subprocess.CompletedProcess([],2,'PRIVATE_ACCOUNT','invalid or expired 2FA code (failureType: 5005) PRIVATE_PASSWORD')
        value=module.probe('binary',self.env,execute=lambda *args,**kwargs:result)
        self.assertEqual(value['status'],'native_verification_rejected')
        self.assertEqual(value['diagnostic']['apple_failure_codes'],[5005])
        for secret in ('PRIVATE_ACCOUNT','PRIVATE_PASSWORD','123456'):self.assertNotIn(secret,json.dumps(value))

    def test_existing_private_cache_is_not_deleted(self):
        folder=Path(self.directory.name)/'.ipatool'/module.hashlib.md5(self.env['APPLE_CN_ID'].encode()).hexdigest()
        folder.mkdir(parents=True);(folder/'account.json').write_text('prior-private-account')
        with self.assertRaisesRegex(module.ChinaAuthError,'china_account_cache_not_empty'):module.probe('binary',self.env)
        self.assertEqual((folder/'account.json').read_text(),'prior-private-account')
if __name__=='__main__':unittest.main()
