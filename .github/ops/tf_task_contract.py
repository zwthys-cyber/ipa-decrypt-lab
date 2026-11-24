"""Source fingerprint for the TestFlight worker's complete verification contract."""
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"))
from native_runtime import fingerprint as base_fingerprint
from tf_task_runtime import fingerprint as runtime_fingerprint
def fingerprint(root=Path(".")):
    root=Path(root);digest=hashlib.sha256(bytes.fromhex(base_fingerprint(root)))
    digest.update(bytes.fromhex(runtime_fingerprint(root)))
    for name in ("tf_task_contract.py","tf_task_worker.py","tf_task_session.py","tf_task_ssh.py","tf_task_transport.py","tf_task_native.cpp",
            "tf_task_runtime.py","tf_virtual_zip_directories.py","tf_virtual_beta_download.py","cn_runtime.py"):
        path=root/".github/ops"/name
        digest.update(name.encode()+b"\0");digest.update(hashlib.sha256(path.read_bytes()).digest())
    for name in (".github/workflows/testflight-private-delivery.yml",".github/workflows/testflight-runtime-build.yml"):
        digest.update(name.encode()+b"\0");digest.update(hashlib.sha256((root/name).read_bytes()).digest())
    return digest.hexdigest()
