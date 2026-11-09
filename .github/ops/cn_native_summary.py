"""One cookie refresh and one native proof-bound read-only CN count query."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from cn_session import decode
from china_auth import failure_diagnostic
from cn_live_auth import seal_session

def trial(binary,env):
    value,_=decode(env)
    base=Path(env['HOME'])/'.ipatool';folder=base/hashlib.md5(value['email'].lower().encode()).hexdigest()
    if base.is_symlink() or folder.exists() or folder.is_symlink():raise ValueError('cache_not_empty')
    base.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700);path=folder/'account.json'
    child={k:env[k] for k in ('HOME','PATH','LANG') if k in env};child['GITHUB_ACTIONS']='true'
    report={'schema':'cn-native-account-count-v1','status':'not_started','computer_count_observed':False,
        'login_attempted':True,'cookie_refresh_attempted':True,'verification_code_used':False,
        'machine_authorization_attempted':False,'deauthorization_attempted':False,'downloaded':False}
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(value['account'],stream)
        for command in ('resume-cn','summary-cn'):
            result=subprocess.run([binary,command,value['email'],'--guid',value['guid']],env=child,
                stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
            if result.returncode:
                report.update(status='cookie_refresh_rejected' if command=='resume-cn' else 'native_summary_rejected',diagnostic=failure_diagnostic(result))
                codes=re.findall(r'^IPA_CN_SUMMARY:HTTP:([1-5][0-9]{2})$',result.stdout,re.M)
                if codes:report['http_status']=int(codes[-1])
                return report
        matches=re.findall(r'^IPA_CN_SUMMARY:COUNT:([0-5])$',result.stdout,re.M)
        if len(matches)!=1:raise ValueError('count_not_observed')
        account=json.loads(path.read_bytes())
        if account.get('store')!='143465' or str(account.get('email','')).casefold()!=value['email'].casefold():raise ValueError('cn_binding')
        seal_session(str(Path(binary).with_name('cn-session-seal')),dict(value,account=account,created=int(time.time())),env)
        report.update(status='computer_count_observed',computer_count_observed=True,authorized_computers=int(matches[0]),session_secret_prepared=True)
        return report
    finally:shutil.rmtree(folder)

def main():
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--binary',required=True);args=p.parse_args()
    try:value=trial(str(Path(args.binary).resolve()),dict(os.environ))
    except Exception:value={'schema':'cn-native-account-count-v1','status':'native_count_probe_failed','computer_count_observed':False,'machine_authorization_attempted':False,'deauthorization_attempted':False}
    Path('cn-session-receipt.json').write_text(json.dumps(value));print(json.dumps(value),flush=True)
    return 0 if value.get('computer_count_observed') is True else 2
if __name__=='__main__':raise SystemExit(main())
