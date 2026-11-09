import json
from pathlib import Path
import unittest
from tf_virtual_transport_patch import patch
from tf_virtual_transport_diagnostics import observations

class TransportControlTests(unittest.TestCase):
    def fixture(self):
        return {"phase":"srp_complete","fresh_connection":True,"curl_exit":28,"http_status":0,
                "connect_ms":10,"tls_ms":40,"first_byte_ms":0,"total_ms":90000,
                "upload_complete":True,"received_body":False,"new_connections":1,"http_version":2}

    def test_closed_diagnostics_discard_raw_logs_and_extra_private_fields(self):
        value=self.fixture()
        raw=b"PRIVATE_ACCOUNT\nTF_NET:"+json.dumps(value).encode()+b"\n"
        self.assertEqual(observations(raw),[value])
        value["email"]="PRIVATE_ACCOUNT"
        self.assertEqual(observations(b"TF_NET:"+json.dumps(value).encode()),[])

    def test_diagnostics_reject_forged_types_and_ranges(self):
        for key,value in (("http_status",True),("phase","PRIVATE"),("connect_ms",-1),("new_connections",100)):
            candidate=self.fixture();candidate[key]=value
            self.assertEqual(observations(b"TF_NET:"+json.dumps(candidate).encode()),[])

    def test_patch_rejects_unpinned_source(self):
        with self.assertRaises(ValueError):patch(b"unreviewed source")

    @unittest.skipUnless(Path("native-source/apple-auth/src/client/transport.cpp").is_file(),"pinned SDK checkout unavailable")
    def test_pinned_control_preserves_tls_checks_and_original_timeout(self):
        raw=Path("native-source/apple-auth/src/client/transport.cpp").read_bytes()
        value=patch(raw)
        for guard in ("CURLOPT_SSL_VERIFYPEER, 1L","CURLOPT_SSL_VERIFYHOST, 2L","CURLOPT_TIMEOUT, 90L"):
            self.assertIn(guard,value)
        self.assertIn("CURLOPT_FRESH_CONNECT, 1L",value)
        self.assertIn("CURLOPT_FORBID_REUSE, 1L",value)
