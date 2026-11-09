"""ARM reference preparation and explicit one-time trial; default is no-account preflight."""
import argparse
import base64
import json
import os
import platform
from pathlib import Path
import signal
import tempfile
from cn_model import base,trial,private,public_preflight
from cn_arm_policy import snapshot,allow_reference,validate_backup
from telegram_queue import failure_kind

def backup(runtime,env):
    if env.get('CN_BACKUP_VERIFY_REQUIRED')=='true' or env.get('CN_RECOVERY_BACKUP_B64'):
        validate_backup(env)
        return {'schema':'cn-arm-backup-receipt-v1','status':'cn_prior_profile_backup_verified',
            'checkpoint_validated':True,'session_guid_bound':True,'backup_roundtrip_verified':True,
            'authorization_request_attempted':False,'deauthorization_attempted':False,'login_attempted':False,'model_recovered':False}
    value=snapshot(env)
    with tempfile.TemporaryDirectory(prefix='cn-prior-profile-private-') as directory:
        root=Path(directory);root.chmod(0o700);path=root/'backup.json'
        path.write_text(json.dumps(value));path.chmod(0o600)
        code,out,_=private([str(runtime/'cn-backup-seal'),str(path)],{'PATH':'/usr/bin:/bin','GITHUB_ACTIONS':'true'},timeout=20)
        if code or not 0<len(out)<=65536:raise ValueError('cn_backup_sealing_failed')
        sealed=json.loads(out)
    if set(sealed)!={'schema','repository','secret_name','key_id','encrypted_value'} or [sealed.get(k) for k in ('schema','repository','secret_name','key_id')]!=['ipa-cn-recovery-backup-secret-v1','zwthys-cyber/ipa-decrypt-lab','CN_RECOVERY_BACKUP_B64','3380204578043523366']:raise ValueError('cn_backup_target_rejected')
    if not 48<len(base64.b64decode(sealed['encrypted_value'],validate=True))<=49152:raise ValueError('cn_backup_ciphertext_bounds')
    sealed.update(auth_run=env['GITHUB_RUN_ID'],commit=env['GITHUB_SHA'])
    Path('cn-recovery-backup-secret-relay.json').write_text(json.dumps(sealed))
    return {'schema':'cn-arm-backup-receipt-v1','status':'cn_prior_profile_backup_prepared','checkpoint_validated':True,
        'session_guid_bound':True,'backup_secret_prepared':True,'authorization_request_attempted':False,
        'deauthorization_attempted':False,'login_attempted':False,'model_recovered':False}

def main():
    os.umask(0o077);p=argparse.ArgumentParser();p.add_argument('--mode',choices=('preflight','backup','trial','replay'),required=True);a=p.parse_args()
    def stop(*_):raise InterruptedError()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    runtime=Path('arm-runtime').resolve();env=dict(os.environ);report=base();report['reference_platform']='macos-15-arm64'
    try:
        if a.mode!='backup' and not (platform.system()=='Darwin' and platform.machine()=='arm64' and platform.mac_ver()[0].split('.')[0]=='15'):raise ValueError('cn_arm_host_rejected')
        if a.mode=='preflight':
            report=public_preflight(runtime);report.update(status='cn_arm_public_preflight_ready',reference_platform='macos-15-arm64')
        elif a.mode=='backup':report=backup(runtime,env)
        else:
            if a.mode=='trial':allow_reference(env)
            trial(runtime,env,a.mode,report,reference_enrollment=a.mode=='trial')
    except Exception as error:
        report.update(status='cn_arm_operation_stopped',private_details_published=False,failure_kind=failure_kind(error))
    report.update(run_id=env.get('GITHUB_RUN_ID'),source_commit=env.get('GITHUB_SHA'))
    name='cn-arm-backup-receipt.json' if a.mode=='backup' else 'cn-model-receipt.json'
    Path(name).write_text(json.dumps(report));print(json.dumps(report),flush=True)
    ready=report.get('status') in ('cn_arm_public_preflight_ready','cn_prior_profile_backup_prepared','cn_prior_profile_backup_verified')
    saved=report.get('checkpoint_saved') is True and report.get('session_secret_prepared') is True and report.get('guid_secret_prepared') is True
    replay=report.get('status')=='cn_replay_session_saved_recovery_pending' and report.get('existing_checkpoint_validated') is True and report.get('session_secret_prepared') is True
    return 0 if ready or saved or replay or report.get('model_secret_prepared') is True else 2
if __name__=='__main__':raise SystemExit(main())
