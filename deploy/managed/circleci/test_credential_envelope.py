import copy
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
import credential_envelope as lease

class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.key=Path(self.temp.name)/"identity.txt"
        result=subprocess.run(["age-keygen","-o",str(self.key)],capture_output=True,check=True)
        recipient=subprocess.check_output(["age-keygen","-y",str(self.key)],text=True).strip()
        self.now=int(time.time())
        self.context=dict(schema="circleci-credential-request-v1",job_id="pilot_"+"a"*32,
            run_id="12345678-1234-1234-1234-123456789abc",
            worker_job_id="23456789-1234-1234-1234-123456789abc",source_sha="b"*40,
            recipient=recipient,nonce="c"*32,expires_at=self.now+300,profile="synthetic")
        self.issuer=dict(os.environ,GITHUB_ACTIONS="true",GITHUB_REPOSITORY=lease.REPO,
                         GITHUB_REF="refs/heads/"+lease.BRANCH,GITHUB_SHA="b"*40)
        self.consumer={k:v for k,v in os.environ.items() if k!="GITHUB_ACTIONS"}
        self.consumer.update(CIRCLECI="true",CIRCLE_BRANCH=lease.BRANCH,CIRCLE_SHA1="b"*40,
                             CIRCLE_WORKFLOW_JOB_ID=self.context["worker_job_id"],
                             RUNTIME_RUN_ID=self.context["run_id"])
        self.values=dict(fixture="synthetic-private-fixture")

    def seal(self):
        return lease.seal(self.context,self.values,self.issuer,self.now)

    def open(self,cipher,context=None):
        return lease.open_envelope(cipher,self.key,context or self.context,self.consumer,self.now)

    def test_catalog_roles_real_age_roundtrip_and_cross_role_rejection(self):
        for role in ("default_catalog","cn_catalog"):
            self.context["profile"]=role
            self.values={key:"synthetic-private-"+key for key in lease.PROFILES[role]}
            cipher=self.seal()
            self.assertEqual(self.open(cipher),self.values)
            for value in self.values.values():self.assertNotIn(value.encode(),cipher)
            other=dict(self.context,profile="cn_catalog" if role=="default_catalog" else "default_catalog")
            with self.assertRaisesRegex(ValueError,"packet_binding"):self.open(cipher,other)

    def test_real_age_roundtrip_and_no_plaintext_cipher(self):
        cipher=self.seal()
        self.assertNotIn(self.values["fixture"].encode(),cipher)
        self.assertEqual(self.open(cipher),self.values)

    def test_different_job_context_cannot_reuse_cipher(self):
        cipher=self.seal()
        altered=dict(self.context,nonce="d"*32)
        with self.assertRaisesRegex(ValueError,"packet_binding"):
            self.open(cipher,altered)

    def test_cipher_tampering_refused(self):
        cipher=self.seal()
        with self.assertRaises(ValueError):
            self.open(cipher[:-20]+b"x"*20)

    def test_forbidden_extra_credentials_refused(self):
        for key in ("TELEGRAM_BOT_TOKEN","CIRCLECI_API_TOKEN","PILOT_DRIVE_REFRESH_TOKEN","APPLE_PASSWORD"):
            with self.assertRaisesRegex(ValueError,"profile_fields"):
                lease.seal(self.context,dict(self.values,**{key:"must-not-leak"}),self.issuer,self.now)

    def test_old_github_flags_are_not_spoofed_on_consumer(self):
        with self.assertRaisesRegex(ValueError,"consumer_context"):
            lease.open_envelope(self.seal(),self.key,self.context,
                                dict(self.consumer,GITHUB_ACTIONS="true"),self.now)

    def test_wrong_run_and_source_refused_before_decryption(self):
        for key,value in (("RUNTIME_RUN_ID",self.context["worker_job_id"]),("CIRCLE_SHA1","f"*40),
                          ("CIRCLE_WORKFLOW_JOB_ID",self.context["run_id"])):
            with self.assertRaisesRegex(ValueError,"consumer_context"):
                lease.open_envelope(self.seal(),self.key,self.context,dict(self.consumer,**{key:value}),self.now)

    def test_wrong_ephemeral_private_key_cannot_open(self):
        other=Path(self.temp.name)/"other-identity.txt"
        subprocess.run(["age-keygen","-o",str(other)],capture_output=True,check=True)
        with self.assertRaisesRegex(ValueError,"decrypt_failed"):
            lease.open_envelope(self.seal(),other,self.context,self.consumer,self.now)

    def test_issuer_rejects_wrong_source_repository_or_branch(self):
        for key,value in (("GITHUB_SHA","f"*40),("GITHUB_REPOSITORY","untrusted/repo"),
                          ("GITHUB_REF","refs/heads/main"),("GITHUB_ACTIONS","false")):
            with self.assertRaisesRegex(ValueError,"issuer_context"):
                lease.seal(self.context,self.values,dict(self.issuer,**{key:value}),self.now)

    def test_expiry_and_key_permissions(self):
        with self.assertRaisesRegex(ValueError,"expired"):
            lease.context(dict(self.context,expires_at=self.now),self.now)
        self.key.chmod(0o644)
        with self.assertRaisesRegex(ValueError,"permissions"):
            self.open(self.seal())

    def test_age_child_process_receives_no_account_or_ci_credentials(self):
        seen=[]
        def execute(args,**kwargs):
            seen.append(kwargs["env"])
            return subprocess.run(args,**kwargs)
        lease.seal(self.context,self.values,dict(self.issuer,APPLE_PASSWORD="synthetic-secret",
                   CF_API_TOKEN="synthetic-token"),self.now,execute)
        self.assertTrue(seen)
        self.assertTrue(all(set(env)<=set(("PATH","HOME","LANG","TMPDIR")) for env in seen))

if __name__=="__main__":
    unittest.main()
