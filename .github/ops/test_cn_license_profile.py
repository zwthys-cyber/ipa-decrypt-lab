import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest
from cn_license_profile import selector,profile,LicenseProfileError
import private_fairplay_state as checkpoint

def atom(name,data):return struct.pack('>I',len(data)+8)+name+data

def fixture(user=123,key=1):return atom(b'sinf',atom(b'schi',atom(b'user',struct.pack('>I',user))+atom(b'key ',struct.pack('>I',key))+atom(b'priv',b'PRIVATE_PAYLOAD'*4)))

class CNLicenseDiagnostics(unittest.TestCase):
    def test_only_nonidentifying_equality_and_geometry_are_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Path(directory);(app/'SC_Info').mkdir();(app/'SC_Info'/'sample.sinf').write_bytes(fixture())
            state={'schema':checkpoint.SCHEMA,'hardware':base64.b64encode(b'ABCDEF').decode(),'files':{'fpsd_sidb':base64.b64encode(b'PRIVATE_STATE').decode()}}
            result=profile(app,'4294967419',base64.b64encode(json.dumps(state).encode()).decode(),'414243444546')
            self.assertTrue(result['sinf_user_equals_account_low32']);self.assertTrue(result['checkpoint_matches_configured_guid'])
            for private in ('PRIVATE','4294967419','414243444546'):self.assertNotIn(private,json.dumps(result))
    def test_duplicate_or_truncated_atoms_fail_closed(self):
        blob=fixture();self.assertEqual(selector(blob)[:2],(123,1))
        with self.assertRaises(LicenseProfileError):selector(blob[:-1])
        duplicate=atom(b'sinf',atom(b'schi',atom(b'user',b'1234')+atom(b'user',b'5678')+atom(b'key ',b'1234')+atom(b'priv',b'private')))
        with self.assertRaises(LicenseProfileError):selector(duplicate)

if __name__=='__main__':unittest.main()
