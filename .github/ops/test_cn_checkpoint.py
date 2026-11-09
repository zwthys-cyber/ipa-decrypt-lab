import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from cn_model import CHECKPOINT_PREFIX
from cn_checkpoint_contract import synthetic,MARKER
import private_fairplay_state as checkpoint

class CNCheckpointDestinationContracts(unittest.TestCase):
    def invoke(self,prefix):
        with tempfile.TemporaryDirectory(prefix=prefix) as directory:
            root=Path(directory);root.chmod(0o700);target=root/'state.json'
            args=['checkpoint','--output',str(target),'--uid',str(os.getuid()),'--gid',str(os.getgid())]
            with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}),patch.object(sys,'platform','darwin'),patch('os.geteuid',return_value=0),patch.object(sys,'argv',args),patch.object(checkpoint,'capture',return_value=synthetic(b'ABCDEF')) as capture,contextlib.redirect_stdout(io.StringIO()):
                code=checkpoint.main()
            if code==0:
                hardware,files=checkpoint.validate(target.read_bytes())
                self.assertEqual(hardware,b'ABCDEF');self.assertEqual(files,{'fpsd_sidb':MARKER})
                self.assertEqual(target.stat().st_mode&0o777,0o600)
            return code,capture.call_count
    def test_real_entrypoint_accepts_the_cn_model_prefix_and_private_permissions(self):
        self.assertEqual(self.invoke(CHECKPOINT_PREFIX),(0,1))
    def test_previous_prefix_is_rejected_before_any_private_state_read(self):
        self.assertEqual(self.invoke('cn-model-private-'),(2,0))

if __name__=='__main__':unittest.main()
