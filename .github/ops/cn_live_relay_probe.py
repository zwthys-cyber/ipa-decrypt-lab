"""Real late encrypted relay with synthetic account/cache; never contacts Apple."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from cn_live_auth import live
from telegram_queue import failure_kind

def main():
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--crypt',required=True);args=p.parse_args()
    report={'schema':'cn-live-relay-probe-v1','synthetic':True,'apple_request_attempted':False,'authorization_request_attempted':False,'status':'failed'}
    try:
        if any(os.environ.get(k) for k in ('APPLE_ID','APPLE_PASSWORD','APPLE_CN_ID','APPLE_CN_PASSWORD','APPLE_CN_SESSION_B64')):raise ValueError()
        with tempfile.TemporaryDirectory(prefix='cn-relay-synthetic-') as directory:
            email='relay-fixture@example.invalid';guid='001122AABBCC'
            account={'email':email,'password':'NOT_A_REAL_PASSWORD','store':'143465','passwordToken':'NOT_A_REAL_TOKEN','directoryServicesIdentifier':'123','cookie':[]}
            value={'schema':'cn-account-session-v1','email':email,'guid':guid,'store':'143465','created':1,'account':account}
            folder=Path(directory)/'.ipatool'/hashlib.md5(email.encode()).hexdigest();folder.mkdir(parents=True,mode=0o700)
            path=folder/'account.json';path.write_text(json.dumps(account));path.chmod(0o600)
            env=dict(os.environ,HOME=directory,APPLE_CN_ID=email,APPLE_CN_GUID=guid,APPLE_CN_SESSION_B64=base64.b64encode(json.dumps(value).encode()).decode())
            program="print('IPA_CN_AUTH:verification_pending',flush=True); assert input()=='000000'; print('synthetic relay accepted')"
            result,_=live('/synthetic/not-executed',str(Path(args.crypt).resolve()),env,
                command=[sys.executable,'-c',program],prepared_session=True,native_guid=guid)
            if result.get('authenticated') is True and result.get('verification_submitted') is True:report['status']='synthetic_late_relay_verified'
    except Exception as error:
        report['failure_kind']=failure_kind(error)
        known={'github_transport_unknown','github_request_rejected','github_permission_denied','cn_code_expired','cn_request_expired','cn_code_decryption_failed','cn_artifact_digest','cn_artifact_inventory','verification_window_expired','authentication_timeout'}
        if str(error) in known:report['error_code']=str(error)
    Path('cn-relay-probe-receipt.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
    return 0 if report['status']=='synthetic_late_relay_verified' else 2
if __name__=='__main__':raise SystemExit(main())
