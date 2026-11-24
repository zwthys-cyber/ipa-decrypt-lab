"""Synthetic state transport tests, no Apple or Telegram traffic."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/".github/ops"))
import tf_state_http as service
import tf_task_transport as transport
from testflight_state import connect,install_cipher,ORIGIN

TOKEN="x"*48
REQUEST=dict(invite="SYNTH123",request_id="tf_"+"a"*32,run_id="123",source_commit="b"*40)
CIPHER=b"age-encryption.org/v1\nsynthetic-not-a-real-session"
ENV=dict(TF_STATE_TRANSPORT="https",TF_STATE_API_URL="https://state.example.invalid",TF_STATE_API_TOKEN=TOKEN)

class StateTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        with patch.dict(os.environ,{},clear=False):
            db=connect(self.root);db.close()
            install_cipher(self.root,dict(schema="tf-durable-state-v1",origin_run=ORIGIN,
                ciphertext_b64=base64.b64encode(CIPHER).decode(),sha256=hashlib.sha256(CIPHER).hexdigest()))
        service.ready(self.root)
        self.server=service.StateServer(("127.0.0.1",0),service.handler(self.root,TOKEN))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(3);self.temp.cleanup()

    def call(self,kind,value,token=TOKEN):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        try:
            conn.request("POST","/v1/"+kind,json.dumps(value),{"Authorization":"Bearer "+token,"Content-Type":"application/json"})
            response=conn.getresponse()
            return response.status,json.loads(response.read())
        finally:conn.close()

    def test_auth_and_closed_operations(self):
        self.assertEqual(self.call("fetch",{},token="wrong")[0],401)
        self.assertEqual(self.call("install",{})[0],404)
        self.assertEqual(self.call("fetch",{"extra":True})[0],409)
        self.assertEqual(self.call("status",{})[0],200)

    def test_cipher_binding(self):
        code,result=self.call("fetch",{})
        self.assertEqual(code,200)
        with patch.object(transport,"https_rpc",return_value=result):
            self.assertEqual(transport.fetch(ENV),CIPHER)
            with patch.object(transport,"https_rpc",return_value=dict(result,sha256="0"*64)):
                with self.assertRaises(ValueError):transport.fetch(ENV)

    def test_durable_denial_and_unknown_outcome(self):
        code,permit=self.call("claim",REQUEST)
        self.assertEqual(code,200);self.assertTrue(permit["permitted"])
        self.assertFalse(self.call("claim",REQUEST)[1]["permitted"])
        finish=dict(REQUEST,nonce=permit["nonce"],outcome="outcome_unknown")
        self.assertEqual(self.call("finish",finish)[0],200)
        self.assertEqual(self.call("finish",finish)[0],200)
        service.ready(self.root)
        self.assertEqual(service.operation(self.root,"claim",REQUEST)["previous_state"],"outcome_unknown")

    def test_no_ssh_fallback(self):
        with patch.object(transport,"https_rpc",side_effect=ValueError),patch.object(transport.tf_task_ssh,"rpc") as ssh:
            with self.assertRaises(ValueError):transport.rpc("claim",REQUEST,ENV)
            ssh.assert_not_called()
        for url in ("http://example.invalid","https://example.invalid/path","https://user@example.invalid","https://example.invalid:8443"):
            with self.assertRaises(ValueError):transport.settings(dict(ENV,TF_STATE_API_URL=url))

    def test_missing_ledger_refused(self):
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(ValueError):service.ready(Path(empty))

if __name__=="__main__":unittest.main()
