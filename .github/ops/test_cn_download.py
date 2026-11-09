import base64
import copy
import io
import json
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
import zipfile
from cn_download_probe import probe,check_metadata,CNDownloadError,TARGET,safe_failure
import test_cn_session

class CNDownloadContracts(unittest.TestCase):
    def metadata(self):return {'resultCount':1,'results':[{'trackId':int(TARGET),'wrapperType':'software','kind':'software','price':0,'currency':'CNY','bundleId':'example.fixture','fileSizeBytes':'2048'}]}
    def test_proof_failure_diagnostic_hides_private_error_details(self):
        value=safe_failure(subprocess.CompletedProcess([],1,'IPA_LAB_STAGE:acquire_free_license','The operation failed. (StoreAMD error 4.) PRIVATE_TOKEN'))
        self.assertTrue(value['store_device_proof_failed']);self.assertNotIn('PRIVATE',json.dumps(value))
    def test_paid_wrong_region_and_oversized_sample_rejected(self):
        for key,value in [('price',1),('currency','EUR'),('trackId',1),('fileSizeBytes',str(201*1024*1024)),('bundleId','bad/../path')]:
            raw=self.metadata();raw['results'][0][key]=value
            with self.assertRaises(CNDownloadError):check_metadata(raw)
    def test_download_restores_only_cn_cache_and_cleans_all_files(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            env=dict(fixture.env(),HOME=directory,PATH='/usr/bin:/bin',LAB_KBSYNC_HELPER='/verified/helper',APPLE_CN_PASSWORD='NEVER_FORWARD',APPLE_ID='NEVER_FORWARD')
            seen=[]
            def execute(argv,**kwargs):
                seen.append(argv[1]);self.assertEqual(argv[1],'download')
                self.assertEqual(set(kwargs['env']),{'HOME','PATH','LAB_KBSYNC_HELPER','GITHUB_ACTIONS'})
                caches=list((Path(directory)/'.ipatool').glob('*/account.json'));self.assertEqual(len(caches),1)
                self.assertEqual(caches[0].stat().st_mode&0o777,0o600)
                self.assertEqual(json.loads(caches[0].read_text())['email'],'cn@example.invalid')
                output=Path(argv[argv.index('--output')+1]);self.output=output
                with zipfile.ZipFile(output,'w') as z:z.writestr('Payload/Sample.app/Info.plist',plistlib.dumps({'CFBundleIdentifier':'example.fixture'}))
                return subprocess.CompletedProcess(argv,0,'PRIVATE_NATIVE_OUTPUT','PRIVATE_PASSWORD')
            result=probe('/verified/client',env,check_metadata(self.metadata()),execute)
            self.assertTrue(result['downloaded']);self.assertFalse(result['login_attempted']);self.assertEqual(seen,['download'])
            self.assertFalse(self.output.exists());self.assertEqual(list((Path(directory)/'.ipatool').iterdir()),[])
            self.assertNotIn('PRIVATE',json.dumps(result))
    def test_cookie_refresh_rejection_never_prompts_or_downloads(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def execute(argv,**kwargs):
                calls.append(argv[1]);return subprocess.CompletedProcess(argv,1,'','apple_auth_ambiguous_bad_login PRIVATE_PASSWORD')
            result=probe('/verified/client',dict(fixture.env(),HOME=directory),check_metadata(self.metadata()),execute,resume=True)
            self.assertEqual(calls,['resume-cn']);self.assertEqual(result['status'],'cn_cookie_refresh_rejected')
            self.assertTrue(result['login_attempted']);self.assertFalse(result['verification_code_used'])
            self.assertNotIn('PRIVATE',json.dumps(result));self.assertEqual(list((Path(directory)/'.ipatool').iterdir()),[])
    def test_refreshed_session_is_sealed_only_after_valid_download(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            calls=[];sealed=[]
            def execute(argv,**kwargs):
                calls.append(argv[1])
                if argv[1]=='resume-cn':return subprocess.CompletedProcess(argv,0,'IPA_CN_RESUME:authenticated','')
                output=Path(argv[argv.index('--output')+1])
                with zipfile.ZipFile(output,'w') as z:z.writestr('Payload/Sample.app/Info.plist',plistlib.dumps({'CFBundleIdentifier':'example.fixture'}))
                return subprocess.CompletedProcess(argv,0,'','')
            def seal(binary,value,env):
                self.assertEqual(binary,'/verified/cn-session-seal');self.assertEqual(value['store'],'143465');sealed.append(True)
            result=probe('/verified/client',dict(fixture.env(),HOME=directory),check_metadata(self.metadata()),execute,resume=True,seal=seal)
            self.assertEqual(calls,['resume-cn','download']);self.assertEqual(sealed,[True]);self.assertTrue(result['session_secret_prepared'])
            self.assertTrue(result['downloaded']);self.assertEqual(list((Path(directory)/'.ipatool').iterdir()),[])
    def test_refusal_cleans_cache_and_does_not_retry_login(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            calls=[]
            def execute(argv,**kwargs):calls.append(argv[1]);return subprocess.CompletedProcess(argv,1,'','failureType: 2034 PRIVATE_PASSWORD')
            result=probe('/verified/client',dict(fixture.env(),HOME=directory),check_metadata(self.metadata()),execute)
            self.assertFalse(result['downloaded']);self.assertEqual(calls,['download']);self.assertNotIn('PRIVATE',json.dumps(result))
            self.assertEqual(list((Path(directory)/'.ipatool').iterdir()),[])

if __name__=='__main__':unittest.main()
