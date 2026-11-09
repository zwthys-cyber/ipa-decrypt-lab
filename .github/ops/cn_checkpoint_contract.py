"""Exercise the real privileged checkpoint destination contract with synthetic state."""
import argparse
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
import private_fairplay_state as checkpoint

MARKER=b'CN_CHECKPOINT_SYNTHETIC_NOT_ACCOUNT_STATE'

def synthetic(hardware):
    value={'schema':checkpoint.SCHEMA,'hardware':base64.b64encode(hardware).decode(),
        'files':{'fpsd_sidb':base64.b64encode(MARKER).decode()}}
    raw=json.dumps(value,separators=(',',':')).encode();checkpoint.validate(raw);return raw

def root_contract():
    value={'schema':'cn-checkpoint-contract-v1','status':'contract_failed','synthetic_state':True,
        'hardware_observed':False,'authorization_request_attempted':False}
    try:
        if os.environ.get('GITHUB_ACTIONS')!='true' or sys.platform!='darwin' or os.geteuid()!=0:raise ValueError()
        result=subprocess.run(['/usr/sbin/ioreg','-a','-l','-r','-k','IOMACAddress','-p','IOService'],
            env={'PATH':'/usr/bin:/bin'},stdin=subprocess.DEVNULL,capture_output=True,timeout=10)
        if result.returncode:raise ValueError()
        hardware=checkpoint.hardware_from_ioreg(result.stdout);value['hardware_observed']=True
        # The production checkpoint entry point and destination checks are unchanged.
        # Only the state reader is replaced, in this separate credential-free contract process.
        checkpoint.capture=lambda:synthetic(hardware)
        result=checkpoint.main()
        value['status']='contract_passed' if result==0 else 'destination_contract_failed'
    except Exception:value['status']='hardware_unavailable' if not value['hardware_observed'] else 'contract_failed'
    print(json.dumps(value),flush=True)
    return 0 if value['status']=='contract_passed' else 2
if __name__=='__main__':raise SystemExit(root_contract())
