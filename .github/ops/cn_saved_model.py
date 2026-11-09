"""Fresh-runner use of the saved CN model; no enrollment or model recovery."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import tempfile
from cn_session import decode,query
from cn_live_auth import live,seal_session
from cn_model import require,private,account_at,bound_env,CNModelError
import private_fairplay_state as checkpoint
from offline_verify import verify,MODEL_LIMIT
from telegram_queue import failure_kind

APPS={'1530340312','1661733229'}
def validated_profile(env):
    require(not any(env.get(k) for k in ('APPLE_ID','APPLE_PASSWORD','FAIRPLAY_MODEL_B64','FAIRPLAY_STATE_B64')),'foreign_account_secrets_present')
    value,_=decode(env)
    hardware,_=checkpoint.validate(checkpoint.decode_bytes(env.get('FAIRPLAY_CN_STATE_B64',''),checkpoint.LIMIT))
    require(hardware.hex().upper()==value['guid'],'cn_saved_checkpoint_guid_mismatch')
    model=checkpoint.decode_bytes(env.get('FAIRPLAY_CN_MODEL_B64',''),MODEL_LIMIT)
    require(len(model)==4184 and model[:8]==b'FPSENR2\x00' and struct.unpack_from('<II',model,8)==(2,len(model)),'cn_saved_model_format_invalid')
    return value

def check(runtime,env,report):
    value=validated_profile(env);report.update(checkpoint_guid_bound=True,model_encoding_validated=True)
    info=json.loads(Path('cn-sample-metadata.json').read_text());app_id=env.get('CN_SAMPLE_APP_ID','1530340312')
    require(app_id in APPS and info.get('app_id')==app_id,'cn_model_sample_binding')
    report['app_id']=app_id
    folder=Path(env['HOME'])/'.ipatool'/hashlib.md5(value['email'].lower().encode()).hexdigest();path=folder/'account.json'
    require(not folder.parent.is_symlink() and not folder.exists() and not folder.is_symlink(),'cn_cache_not_empty')
    folder.parent.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700)
    child={k:env[k] for k in ('HOME','PATH','LANG','LAB_KBSYNC_HELPER') if k in env};child['GITHUB_ACTIONS']='true'
    binary=str(runtime/'ApplePackageTool')
    try:
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(descriptor,'w') as target:json.dump(value['account'],target)
        report['stage']='authenticating'
        authenticated,current=live(binary,str(runtime/'delivery-crypt'),env,prepared_session=True,native_guid=value['guid'])
        require(authenticated.get('authenticated') is True,'cn_saved_model_authentication_rejected')
        report.update(cookie_refresh_authenticated=True,verification_code_used=authenticated.get('verification_submitted') is True)
        account_at(path,value);report['stage']='count_query'
        count=query(bound_env(env,current));require(count.get('session_reused') is True,'cn_saved_model_count_unavailable')
        report['authorized_computers']=count['authorized_computers']
        with tempfile.TemporaryDirectory(prefix='cn-saved-model-private-') as directory:
            root=Path(directory);root.chmod(0o700);ipa=root/'original.ipa';report['stage']='download'
            code,_,_=private([binary,'download',value['email'],info['bundle_id'],'--guid',value['guid'],'--output',str(ipa)],child,timeout=300)
            require(code==0 and ipa.is_file() and not ipa.is_symlink() and 0<ipa.stat().st_size<=200*1024*1024,'cn_saved_model_download_failed')
            report.update(downloaded=True,ipa_bytes=ipa.stat().st_size,stage='saved_model_verification')
            os.environ['FAIRPLAY_MODEL_B64']=env['FAIRPLAY_CN_MODEL_B64']
            try:checked=verify(str(runtime/'offline-engine'),ipa)
            finally:os.environ.pop('FAIRPLAY_MODEL_B64',None)
            report['verification']=checked
            require(checked.get('decryption_proven') is True and checked.get('plaintext_verified') is True,'cn_saved_model_plaintext_not_verified')
            current['account']=account_at(path,value);seal_session(str(runtime/'cn-session-seal'),current,env)
            report.update(status='cn_saved_model_reused_and_verified',model_reused=True,decryption_proven=True,
                plaintext_verified=True,session_secret_prepared=True)
    finally:
        if folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

def main():
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);a=p.parse_args()
    def stop(*_):raise InterruptedError()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    report={'schema':'cn-saved-model-verification-v1','profile':'cn','store':'143465','status':'not_started',
        'authorization_request_attempted':False,'deauthorization_attempted':False,'model_recovery_attempted':False,
        'model_reused':False,'decryption_proven':False,'plaintext_verified':False,'runtime_verified':False,
        'plaintext_retained':False,'verification_code_used':False,'stage':'profile_validation'}
    try:
        require(os.environ.get('GITHUB_ACTIONS')=='true','requires_github_actions')
        check(Path(a.runtime).resolve(),dict(os.environ),report)
    except CNModelError as error:report['status']=str(error)
    except Exception as error:report.update(status='cn_saved_model_check_stopped',failure_kind=failure_kind(error))
    report.update(run_id=os.environ.get('GITHUB_RUN_ID'),source_commit=os.environ.get('GITHUB_SHA'))
    Path('cn-saved-model-receipt.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
    return 0 if report.get('status')=='cn_saved_model_reused_and_verified' else 2
if __name__=='__main__':raise SystemExit(main())
