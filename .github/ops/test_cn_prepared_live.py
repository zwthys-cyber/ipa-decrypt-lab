import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from cn_live_auth import live
import test_cn_session

class CNPreparedLiveContracts(unittest.TestCase):
    def test_prepared_secret_preserves_cache_and_accepts_bound_native_identity(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'.ipatool'/hashlib.md5(fixture.value['email'].encode()).hexdigest();folder.mkdir(parents=True,mode=0o700)
            cache=folder/'account.json';cache.write_text(json.dumps(fixture.value['account']));cache.chmod(0o600)
            env=dict(fixture.env(),HOME=directory,PATH=os.environ.get('PATH','/usr/bin:/bin'),GITHUB_RUN_ID='123',GITHUB_SHA='a'*40,CN_HANDSHAKE_FILE=str(Path(directory)/'waiting.json'))
            script="import os; assert 'APPLEPACKAGE_PASSWORD' not in os.environ; print('PRIVATE_NATIVE_OUTPUT')"
            with patch('builtins.print') as printed:
                result,envelope=live('/verified/tool','/verified/crypt',env,command=[sys.executable,'-c',script],prepared_session=True,native_guid='AABBCCDDEEFF')
            self.assertTrue(result['authenticated']);self.assertEqual(envelope['guid'],'AABBCCDDEEFF')
            self.assertTrue(cache.exists());self.assertEqual(printed.call_count,0)
    def test_prepared_cache_must_match_the_protected_secret(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'.ipatool'/hashlib.md5(fixture.value['email'].encode()).hexdigest();folder.mkdir(parents=True)
            cache=folder/'account.json';value=dict(fixture.value['account'],passwordToken='WRONG_ACCOUNT_TOKEN');cache.write_text(json.dumps(value));cache.chmod(0o600)
            env=dict(fixture.env(),HOME=directory)
            with patch('subprocess.Popen') as start:
                with self.assertRaises(Exception):live('/tool','/crypt',env,prepared_session=True,native_guid='AABBCCDDEEFF')
                start.assert_not_called()
            self.assertTrue(cache.exists())

if __name__=='__main__':unittest.main()
