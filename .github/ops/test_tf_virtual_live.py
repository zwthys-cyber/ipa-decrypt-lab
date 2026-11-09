import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from tf_virtual_live import envelope,decrypt_cipher,relay_url

class LiveRelayTests(unittest.TestCase):
    def waiting(self):
        return {"schema":"cn-live-request-v1","auth_run":"42","commit":"a"*40,
                "nonce":"b"*32,"expires":int(time.time())+300}

    def test_packet_rejects_wrong_source_run_nonce_and_plaintext_fields(self):
        waiting=self.waiting()
        value={"schema":"tf-virtual-live-relay-v1","auth_run":"42","commit":"a"*40,
               "nonce":"b"*32,"ciphertext_b64":base64.b64encode(b"age-encryption.org/v1\nSYNTHETIC").decode()}
        self.assertTrue(envelope(value,waiting))
        for key,bad in (("auth_run","43"),("commit","c"*40),("nonce","d"*32),("code","123456")):
            changed={**value,key:bad}
            with self.assertRaises(ValueError):envelope(changed,waiting)

    def test_source_url_is_fixed_and_expired_waiter_is_rejected(self):
        waiting=self.waiting()
        self.assertTrue(relay_url(waiting).startswith("https://raw.githubusercontent.com/zwthys-cyber/ipa-decrypt-lab/tf-virtual-code-42-"))
        waiting["expires"]=int(time.time())-1
        with self.assertRaises(Exception):relay_url(waiting)

    @unittest.skipUnless(shutil.which("age") and shutil.which("age-keygen"),"age runtime unavailable")
    def test_real_encryption_roundtrip_is_bound_to_waiting_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);identity=root/"identity"
            subprocess.run(["age-keygen","-o",str(identity)],capture_output=True,check=True)
            recipient=subprocess.run(["age-keygen","-y",str(identity)],capture_output=True,check=True).stdout.decode().strip()
            waiting=self.waiting()
            payload={"schema":"cn-live-code-v1",**{k:waiting[k] for k in ("auth_run","commit","nonce")},
                     "issued_at":int(time.time()),"code":"123456"}
            cipher=subprocess.run(["age","-r",recipient],input=json.dumps(payload).encode(),capture_output=True,check=True).stdout
            env={**os.environ,"RUNNER_TEMP":folder}
            self.assertEqual(decrypt_cipher(cipher,waiting,identity.read_text(),env),"123456")
            changed={**waiting,"nonce":"c"*32}
            with self.assertRaises(Exception):decrypt_cipher(cipher,changed,identity.read_text(),env)
