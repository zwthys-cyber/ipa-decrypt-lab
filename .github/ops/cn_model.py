"""Bounded CN-only enrollment/recovery, with a checkpoint before model recovery."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from cn_session import decode,query,UA
from cn_live_auth import seal_session,live
from telegram_queue import failure_kind
from china_auth import failure_diagnostic
from cn_download_probe import TARGET,LIMIT
from machine_enrollment import clean,COMMERCE_READY,stop_private_group
from fairplay_state_observer import collect
from model_bootstrap import candidate_app,input_profile,state_ready,setup_summary,recovery_diagnostics,recover_checkpoint
from offline_verify import verify
import private_fairplay_state as checkpoint

CHECKPOINT_PREFIX='ipa-lab-model-bootstrap-cn-'

class CNModelError(ValueError):pass

def require(value,label):
    if not value:raise CNModelError(label)

def private(argv,env,*,data=None,timeout=120):
    process=subprocess.Popen(argv,env=env,stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:out,err=process.communicate(data,timeout=timeout)
    except BaseException:
        stop_private_group(process,elevated=argv[:2]==['/usr/bin/sudo','-n'])
        process.communicate(timeout=5);raise
    return process.returncode,out,err

def account_at(path,value):
    require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0 and 0<path.stat().st_size<=32768,'private_cn_cache_invalid')
    account=json.loads(path.read_bytes())
    original=value['account']
    require(isinstance(account,dict) and account.get('store')=='143465'
        and str(account.get('email','')).casefold()==value['email'].casefold()
        and account.get('directoryServicesIdentifier')==original.get('directoryServicesIdentifier')
        and isinstance(account.get('passwordToken'),str) and bool(account['passwordToken']),'cn_account_binding_failed')
    return account

def payload(value,account,guid):
    require(isinstance(guid,str) and re.fullmatch(r'[A-F0-9]{12}',guid),'cn_native_guid_invalid')
    require(account.get('store')=='143465' and str(account.get('email','')).casefold()==value['email'].casefold()
        and account.get('directoryServicesIdentifier')==value['account'].get('directoryServicesIdentifier'),'cn_account_binding_failed')
    return {'dsid':account['directoryServicesIdentifier'],'token':account['passwordToken'],'guid':guid,
        'cookies':account['cookie'],'client_context':'login_agent','user_agent':UA,'backend':'commerce','apple_id':value['email']}

def gate(count,profile,prepared,observation):
    require(count.get('session_reused') is True and count.get('http_status')==200
        and type(count.get('authorized_computers')) is int and 0<=count['authorized_computers']<5,'cn_computer_quota_unavailable')
    require(profile.get('ready') is True,'cn_input_profile_not_ready')
    require(prepared.get('status')=='commerce_request_prepared' and prepared.get('authorization_request_attempted') is False
        and prepared.get('running_as_root') is False and all(prepared.get(k) is True for k in COMMERCE_READY),'cn_native_binding_not_ready')
    require(observation.get('root_status')=='observed','cn_state_observer_not_ready')

def authorization_outcome(raw):
    require(isinstance(raw,dict) and raw.get('schema')=='ipa-lab-machine-enrollment-v1'
        and type(raw.get('authorization_request_attempted')) is bool,'cn_authorization_outcome_unknown_do_not_retry')
    result=clean(raw);attempted=result.get('authorization_request_attempted') is True
    complete=result.get('http_status')==200 and type(result.get('apple_failure_present')) is bool
    definitive=complete and (result['apple_failure_present'] is True or result.get('keybag_present') is True)
    return result,attempted and not definitive

def seal_file(sealer,path,purpose,env):
    arguments=[sealer,str(path)]+([] if purpose=='model' else [purpose])
    code,out,_=private(arguments,{'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'},timeout=20)
    require(code==0 and 0<len(out)<=65536,'cn_private_sealing_failed')
    value=json.loads(out)
    secrets={'model':'FAIRPLAY_CN_MODEL_B64','state':'FAIRPLAY_CN_STATE_B64','guid':'APPLE_CN_GUID'}
    schemas={'model':'ipa-lab-github-sealed-model-v1','state':'ipa-lab-github-sealed-state-v1','guid':'ipa-lab-github-sealed-cn-guid-v1'}
    require(set(value)=={'schema','repository','secret_name','key_id','encrypted_value'}
        and value['schema']==schemas[purpose] and value['secret_name']==secrets[purpose]
        and value['repository']=='zwthys-cyber/ipa-decrypt-lab' and value['key_id']=='3380204578043523366','cn_sealed_destination_invalid')
    cipher=base64.b64decode(value['encrypted_value'],validate=True);require(48<len(cipher)<=44*1024+48,'cn_ciphertext_size')
    value.update(auth_run=env['GITHUB_RUN_ID'],commit=env['GITHUB_SHA'])
    Path('cn-'+purpose+'-secret-relay.json').write_text(json.dumps(value))

def checkpoint_file(root):
    path=root/'state.json'
    argv=['/usr/bin/sudo','-n','--','/usr/bin/env','-i','PATH=/usr/bin:/bin','GITHUB_ACTIONS=true',
        str(Path(sys.executable).resolve()),str(Path(checkpoint.__file__).resolve()),'--output',str(path),'--uid',str(os.getuid()),'--gid',str(os.getgid())]
    code,_,_=private(argv,{'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'},timeout=25)
    require(code==0 and path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0,'cn_checkpoint_capture_failed')
    checkpoint.validate(path.read_bytes());return path

def bound_env(env,value):
    return dict(env,APPLE_CN_GUID=value['guid'],APPLE_CN_SESSION_B64=base64.b64encode(json.dumps(value).encode()).decode())

def base():
    return {'schema':'cn-model-bootstrap-v1','profile':'cn','store':'143465','app_id':TARGET,'status':'not_started',
        'authorization_request_attempted':False,'authorization_outcome_uncertain':False,'deauthorization_attempted':False,
        'verification_code_used':False,'model_recovered':False,'decryption_proven':False,'plaintext_verified':False,
        'runtime_verified':False,'plaintext_retained':False,'checkpoint_saved':False,'model_secret_prepared':False}

def trial(runtime,env,mode,report):
    require(not any(env.get(k) for k in ('APPLE_ID','APPLE_PASSWORD','FAIRPLAY_MODEL_B64','FAIRPLAY_STATE_B64')),'foreign_account_secrets_present')
    require(mode in ('trial','replay'),'cn_model_mode_invalid')
    require(mode=='replay' or env.get('CN_MODEL_STATE_PRESENT')!='true','cn_saved_state_requires_replay')
    if mode=='replay':checkpoint.validate(checkpoint.decode_bytes(env.get('FAIRPLAY_CN_STATE_B64',''),checkpoint.LIMIT))
    report['checkpoint_preflight']=checkpoint_preflight()
    value,_=decode(env);info=json.loads(Path('cn-sample-metadata.json').read_text())
    require(info.get('app_id')==TARGET,'cn_sample_binding')
    binary=str(runtime/'ApplePackageTool');engine=str(runtime/'offline-engine');sealer=str(runtime/'cn-model-seal')
    child={k:env[k] for k in ('HOME','PATH','LANG','LAB_KBSYNC_HELPER') if k in env};child['GITHUB_ACTIONS']='true'
    guid=value['guid']
    if mode=='trial':
        code,raw,_=private([str(runtime/'native-device-identity')],child,timeout=10)
        require(code==0 and re.fullmatch(rb'[A-F0-9]{12}',raw),'cn_native_identity_unavailable');guid=raw.decode()
    report['native_guid_rotation_required']=guid!=value['guid']
    folder=Path(env['HOME'])/'.ipatool'/hashlib.md5(value['email'].lower().encode()).hexdigest()
    require(not folder.parent.is_symlink() and not folder.exists() and not folder.is_symlink(),'cn_cache_not_empty')
    folder.parent.mkdir(mode=0o700,exist_ok=True);folder.mkdir(mode=0o700);path=folder/'account.json'
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as stream:json.dump(value['account'],stream)
        report['stage']='authenticating'
        authenticated,current=live(binary,str(runtime/'delivery-crypt'),env,prepared_session=True,native_guid=guid)
        if authenticated.get('authenticated') is not True:
            report.update(status='cn_cookie_refresh_rejected',diagnostic=authenticated.get('diagnostic',{}));return
        report['verification_code_used']=authenticated.get('verification_submitted') is True
        account=account_at(path,value)
        report['cookie_refresh_authenticated']=True
        report['stage']='count_query'
        count=query(bound_env(env,current));report['count_query']=count
        require(count.get('session_reused') is True,'cn_computer_count_unavailable')
        report['account_count_before']=count['authorized_computers']
        with tempfile.TemporaryDirectory(prefix=CHECKPOINT_PREFIX) as directory:
            root=Path(directory);root.chmod(0o700);ipa=root/'original.ipa'
            report['stage']='download'
            code,out,err=private([binary,'download',value['email'],info['bundle_id'],'--guid',guid,'--output',str(ipa)],child,timeout=300)
            require(code==0 and ipa.is_file() and not ipa.is_symlink() and 0<ipa.stat().st_size<=LIMIT,'cn_original_download_failed')
            report['downloaded']=True;report['ipa_bytes']=ipa.stat().st_size
            app=candidate_app(ipa,root/'candidate');profile=input_profile(engine,ipa);report['input_profile']=profile
            require(profile.get('ready') is True,'cn_input_profile_not_ready')
            if mode=='trial':
                prepared_path=root/'prepared.json'
                fixed=json.dumps({'guid':guid,'user_agent':UA}).encode()
                code,_,_=private([str(runtime/'native-machine-enrollment'),'--prepare-probe',str(prepared_path)],child,data=fixed,timeout=45)
                require(code==0 and prepared_path.is_file() and prepared_path.stat().st_size<=65536,'cn_native_preflight_failed')
                prepared=clean(json.loads(prepared_path.read_text()));report['native_preflight']=prepared
                report['checkpoint_preflight']=checkpoint_preflight(guid)
                before=collect();gate(count,profile,prepared,before)
                native_report=root/'enrollment.json';native_input=json.dumps(payload(value,account,guid)).encode()
                report['stage']='authorizing'
                report['authorization_outcome_uncertain']=True
                code,_,_=private([str(runtime/'native-machine-enrollment'),str(native_report)],child,data=native_input,timeout=80)
                require(code==0 and native_report.is_file() and native_report.stat().st_size<=65536,'cn_authorization_outcome_unknown_do_not_retry')
                result,uncertain=authorization_outcome(json.loads(native_report.read_text()));report['authorization_outcome_uncertain']=uncertain
                report['authorization_request_attempted']=result.get('authorization_request_attempted') is True
                result.update(store_session_authenticated=True,state_observation_before=before,state_observation_after=collect())
                after=query(bound_env(env,current));report['count_query_after']=after
                if after.get('session_reused') is True:report['account_count_after']=after['authorized_computers']
                report['enrollment']=result
                require(state_ready(result),'cn_enrollment_state_unavailable_do_not_repeat')
                report['stage']='checkpoint_capture'
                saved=checkpoint_file(root);seal_file(sealer,saved,'state',env);report['checkpoint_saved']=True
                guid_file=root/'guid.txt';guid_file.write_text(guid);guid_file.chmod(0o600);seal_file(sealer,guid_file,'guid',env)
                current['account']=account_at(path,value);seal_session(str(runtime/'cn-session-seal'),current,env)
                report['session_secret_prepared']=True;report['guid_secret_prepared']=True
            else:report['existing_checkpoint_validated']=True
            report['stage']='model_recovery'
            models=root/'models'
            if mode=='trial':models.mkdir(mode=0o700)
            model_env={'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'}
            if mode=='replay':
                os.environ['FAIRPLAY_STATE_B64']=env['FAIRPLAY_CN_STATE_B64']
                try:code,out,err=recover_checkpoint(engine,app,ipa,root,models)
                finally:os.environ.pop('FAIRPLAY_STATE_B64',None)
            else:
                argv=['/usr/bin/sudo','-n','--','/usr/bin/env','-i','PATH=/usr/bin:/bin','GITHUB_ACTIONS=true',
                    'TMPDIR='+str(root),'SUDO_UID='+str(os.getuid()),'SUDO_GID='+str(os.getgid()),engine,'setup','--app',str(app),'--ipa',str(ipa),'--model-dir',str(models)]
                code,out,err=private(argv,model_env,timeout=300)
            if code:
                report.update(status='cn_checkpoint_ready_model_recovery_pending' if report['checkpoint_saved'] else 'cn_model_recovery_rejected',recovery_diagnostics=recovery_diagnostics(out+err));return
            model,setup=setup_summary(out,models,**({'schema':'unfairplay-enrollment-recovery-v1','model_key':'enrollment_model'} if mode=='replay' else {}))
            report.update(setup,model_recovered=True)
            os.environ['FAIRPLAY_MODEL_B64']=base64.b64encode(model.read_bytes()).decode()
            try:checked=verify(engine,ipa)
            finally:os.environ.pop('FAIRPLAY_MODEL_B64',None)
            report['verification']=checked
            require(checked.get('decryption_proven') is True and checked.get('plaintext_verified') is True,'cn_model_plaintext_not_verified')
            seal_file(sealer,model,'model',env)
            report.update(status='cn_model_recovered_and_verified',decryption_proven=True,plaintext_verified=True,model_secret_prepared=True)
    finally:
        if folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

def checkpoint_preflight(expected_guid=None):
    with tempfile.TemporaryDirectory(prefix=CHECKPOINT_PREFIX) as directory:
        root=Path(directory);root.chmod(0o700);path=root/'state.json'
        argv=['/usr/bin/sudo','-n','--','/usr/bin/env','-i','PATH=/usr/bin:/bin','GITHUB_ACTIONS=true',
            str(Path(sys.executable).resolve()),str(Path(__file__).with_name('cn_checkpoint_contract.py').resolve()),
            '--output',str(path),'--uid',str(os.getuid()),'--gid',str(os.getgid())]
        code,out,_=private(argv,{'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'},timeout=25)
        records=[]
        for line in out.splitlines():
            try:records.append(json.loads(line))
            except Exception:pass
        receipt=next((x for x in records if x.get('schema')=='cn-checkpoint-contract-v1'),{})
        require(code==0 and receipt.get('status')=='contract_passed' and receipt.get('hardware_observed') is True,'cn_checkpoint_preflight_failed')
        require(path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0 and path.stat().st_uid==os.getuid(),'cn_checkpoint_preflight_permissions')
        hardware,files=checkpoint.validate(path.read_bytes())
        require(files=={'fpsd_sidb':b'CN_CHECKPOINT_SYNTHETIC_NOT_ACCOUNT_STATE'},'cn_checkpoint_preflight_fixture')
        if expected_guid is not None:
            require(hardware.hex().upper()==expected_guid,'cn_checkpoint_native_identity_mismatch')
            receipt['native_identity_matched']=True
        return receipt

def public_preflight(runtime):
    require(os.environ.get('GITHUB_ACTIONS')=='true','requires_github_actions')
    require(not any(os.environ.get(k) for k in ('APPLE_CN_ID','APPLE_CN_PASSWORD','APPLE_CN_SESSION_B64','APPLE_ID','APPLE_PASSWORD')),'preflight_received_credentials')
    env={k:os.environ[k] for k in ('HOME','PATH','LANG') if k in os.environ};env['GITHUB_ACTIONS']='true'
    code,raw,_=private([str(runtime/'native-device-identity')],env,timeout=10)
    require(code==0 and re.fullmatch(rb'[A-F0-9]{12}',raw),'cn_native_identity_unavailable')
    with tempfile.TemporaryDirectory(prefix='cn-public-model-preflight-') as directory:
        path=Path(directory)/'prepared.json'
        code,_,_=private([str(runtime/'native-machine-enrollment'),'--prepare-probe',str(path)],env,data=json.dumps({'guid':raw.decode(),'user_agent':UA}).encode(),timeout=45)
        require(code==0 and path.is_file() and path.stat().st_size<=65536,'cn_native_preflight_failed')
        prepared=clean(json.loads(path.read_text()))
    require(prepared.get('status')=='commerce_request_prepared' and prepared.get('authorization_request_attempted') is False,'cn_native_preflight_failed')
    saved=checkpoint_preflight(raw.decode())
    return dict(base(),status='cn_native_preflight_ready',native_preflight=prepared,checkpoint_preflight=saved)

def main():
    os.umask(0o077);parser=argparse.ArgumentParser();parser.add_argument('--runtime',required=True);parser.add_argument('--mode',choices=('preflight','trial','replay'),required=True);args=parser.parse_args()
    def stop(*_):raise InterruptedError()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    report=base()
    try:
        if args.mode=='preflight':report=public_preflight(Path(args.runtime).resolve())
        else:trial(Path(args.runtime).resolve(),dict(os.environ),args.mode,report)
    except CNModelError as error:report['status']=str(error)
    except subprocess.TimeoutExpired:report['status']='cn_model_timeout_do_not_repeat'
    except Exception as error:
        report['status']='cn_model_trial_stopped_do_not_repeat';report['failure_kind']=failure_kind(error)
        known={'github_transport_unknown','github_request_rejected','github_permission_denied','cn_code_expired','cn_request_expired','cn_code_decryption_failed','cn_artifact_digest','cn_artifact_inventory','prepared_cn_cache_binding','prepared_cn_cache_invalid','cn_session_binding','verification_window_expired','authentication_timeout'}
        if str(error) in known:report['error_code']=str(error)
    report.update(run_id=os.environ.get('GITHUB_RUN_ID'),source_commit=os.environ.get('GITHUB_SHA'))
    Path('cn-model-receipt.json').write_text(json.dumps(report));print(json.dumps(report),flush=True)
    # A preserved authenticated checkpoint is a completed stage, never a claim of recovered model.
    return 0 if report.get('status')=='cn_native_preflight_ready' or report.get('model_secret_prepared') is True or report.get('checkpoint_saved') is True and report.get('session_secret_prepared') is True and report.get('guid_secret_prepared') is True else 2
if __name__=='__main__':raise SystemExit(main())
