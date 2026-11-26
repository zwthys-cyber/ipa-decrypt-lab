"""CI-only synthetic ciphertext retention boundaries; never decrypt or access private state."""
import base64
import hashlib
import unittest
from unittest.mock import patch
import retain_canary_archive as archive

class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.raw=b"age-encryption.org/v1\n"+b"synthetic-encrypted-bytes"*2500
        self.digest=hashlib.sha256(self.raw).hexdigest()
        self.guard=patch.object(archive,"DIGEST",self.digest);self.guard.start();self.addCleanup(self.guard.stop)
        self.metadata=dict(id=archive.ARTIFACT,name="circleci-owner-canary-"+str(archive.RUN),expired=False,
            workflow_run=dict(id=archive.RUN,head_sha=archive.SOURCE,repository_id=1444792484,
                head_repository_id=1444792484,head_branch=archive.BRANCH))
        self.index=archive.manifest(self.raw)
        self.env={name:base64.b64encode(self.raw[i*archive.CHUNK:(i+1)*archive.CHUNK]).decode()
            for i,name in enumerate(self.index["chunks"])}

    def test_complete_copy_roundtrip_retains_no_cutover_authority(self):
        self.assertEqual(archive.validate(self.raw,self.metadata),self.raw)
        self.assertEqual(archive.assemble(self.index,self.env),self.raw)
        self.assertFalse(self.index["permanent_handoff"])
        self.assertTrue(all(name.startswith("CIRCLECI_CANARY_") for name in self.index["chunks"]))

    def test_tamper_missing_reordered_or_oversized_chunk_rejected(self):
        for env in (dict(self.env,**{self.index["chunks"][0]:""}),dict(self.env,**{self.index["chunks"][0]:base64.b64encode(b"bad").decode()})):
            with self.assertRaises(ValueError):archive.assemble(self.index,env)
        for index in (dict(self.index,chunks=list(reversed(self.index["chunks"]))),dict(self.index,permanent_handoff=True),
                      dict(self.index,archive_bytes=archive.CHUNK*21),dict(self.index,archive_bytes=True)):
            with self.assertRaises(ValueError):archive.assemble(index,self.env)

    def test_artifact_provenance_expiry_and_digest_are_required(self):
        for metadata in (dict(self.metadata,id=1),dict(self.metadata,expired=True),
                         dict(self.metadata,workflow_run=dict(self.metadata["workflow_run"],head_sha="0"*40))):
            with self.assertRaises(ValueError):archive.validate(self.raw,metadata)
        with self.assertRaises(ValueError):archive.validate(self.raw+b"tamper",self.metadata)

if __name__=="__main__":unittest.main()
