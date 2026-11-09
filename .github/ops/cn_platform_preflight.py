"""Credential-free native platform comparison; no authorization or model output."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
from cn_model import public_preflight

REFERENCE='1e58d37e9602dd0ca5e24b14762063b6c310248b4d3a94272771d815e4ea1784'
POOLS={'macos-15':'arm64','macos-26-intel':'x86_64'}
def summary(pool,architecture,build,reference_match,ready):
    if pool not in POOLS or architecture!=POOLS[pool] or not re.fullmatch('[A-Za-z0-9]{1,32}',build):raise ValueError('public_platform_binding')
    if type(reference_match) is not bool or type(ready) is not bool:raise ValueError('public_platform_proof')
    return {'schema':'cn-public-platform-preflight-v1','pool':pool,'architecture':architecture,'macos_build':build,
        'native_constructor_ready':ready,'reference_binary_match':reference_match,
        'credentials_loaded':False,'authorization_request_attempted':False,'deauthorization_attempted':False,
        'model_recovered':False,'platform_decryption_proven':False}

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or sys.platform!='darwin':raise ValueError('requires_github_macos')
    if any(k.startswith(('APPLE_','FAIRPLAY_','DELIVERY_','TELEGRAM_')) and v for k,v in os.environ.items()):raise ValueError('public_preflight_received_secrets')
    pool=os.environ['CN_PUBLIC_POOL'];architecture=platform.machine()
    build=subprocess.check_output(['/usr/bin/sw_vers','-buildVersion'],env={'PATH':'/usr/bin:/bin'},timeout=10).decode().strip()
    binary=Path('/usr/libexec/fairplayd');match=False
    if binary.is_file() and not binary.is_symlink() and 0<binary.stat().st_size<=128*1024*1024:
        match=hashlib.sha256(binary.read_bytes()).hexdigest()==REFERENCE
    result=public_preflight(Path('public-native').resolve())
    ready=result.get('status')=='cn_native_preflight_ready' and result.get('checkpoint_preflight',{}).get('native_identity_matched') is True
    report=summary(pool,architecture,build,match,ready)
    report.update(run_id=os.environ['GITHUB_RUN_ID'],source_commit=os.environ['GITHUB_SHA'])
    Path('cn-public-platform.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
    return 0 if ready else 2
if __name__=='__main__':raise SystemExit(main())
