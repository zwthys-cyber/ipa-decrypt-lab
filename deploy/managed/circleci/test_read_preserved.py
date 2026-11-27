import base64
import hashlib
import unittest
import read_preserved as state
class ReadbackTests(unittest.TestCase):
    def fixture(self):
        raw=b"age-encryption.org/v1\nsynthetic-private-cipher"
        name="CIRCLECI_MIGRATION_123_01"
        pins=dict(schema="circleci-preserved-source-v1",frozen=False,cutover_approved=False,
            recipient=state.RECIPIENT,source_run=123,chunks=[name],archive_bytes=len(raw),
            archive_sha256=hashlib.sha256(raw).hexdigest())
        return pins,{name:base64.b64encode(raw).decode()},raw
    def test_exact_cipher_reassembly(self):
        pins,env,raw=self.fixture();self.assertEqual(state.reassemble(pins,env),raw)
    def test_tamper_missing_part_or_foreign_secret_name_fails(self):
        pins,env,raw=self.fixture()
        with self.assertRaises(ValueError):state.reassemble(pins,{})
        with self.assertRaises(ValueError):state.reassemble(dict(pins,archive_sha256="a"*64),env)
        with self.assertRaises(ValueError):state.reassemble(dict(pins,chunks=["TELEGRAM_BOT_TOKEN"]),{"TELEGRAM_BOT_TOKEN":"secret"})
    def test_a_live_copy_cannot_be_claimed_as_frozen_or_approved(self):
        pins,env,raw=self.fixture()
        for key in ("frozen","cutover_approved"):
            with self.assertRaises(ValueError):state.reassemble(dict(pins,**{key:True}),env)
if __name__=="__main__":unittest.main()
