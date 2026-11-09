"""Explicit one-run ARM reference enrollment, gated before account access."""
import base64
import hmac
import json
import platform
import re
import time
from cn_session import decode
from telegram_queue import GitHub
import private_fairplay_state as checkpoint

REPOSITORY='zwthys-cyber/ipa-decrypt-lab'
WORKFLOW='.github/workflows/cn-arm-model-bootstrap.yml'
class CNReferenceError(ValueError):pass

def require(value):
    if not value:raise CNReferenceError('cn_arm_reference_gate_rejected')

def snapshot(env):
    value,_=decode(env)
    hardware,_=checkpoint.validate(checkpoint.decode_bytes(env.get('FAIRPLAY_CN_STATE_B64',''),checkpoint.LIMIT))
    require(hardware.hex().upper()==value['guid'])
    return {'schema':'cn-arm-prior-profile-v1','guid':value['guid'],
        'session_b64':env['APPLE_CN_SESSION_B64'],'state_b64':env['FAIRPLAY_CN_STATE_B64']}

def validate_backup(env):
    raw=checkpoint.decode_bytes(env.get('CN_RECOVERY_BACKUP_B64',''),32768)
    value=json.loads(raw)
    require(type(value) is dict and set(value)=={'schema','guid','session_b64','state_b64'})
    require(hmac.compare_digest(json.dumps(value,sort_keys=True).encode(),json.dumps(snapshot(env),sort_keys=True).encode()))
    return value

def allow_reference(env,now=None):
    require(env.get('GITHUB_ACTIONS')=='true' and env.get('GITHUB_REPOSITORY')==REPOSITORY
        and env.get('GITHUB_WORKFLOW_REF')==REPOSITORY+'/'+WORKFLOW+'@refs/heads/main'
        and env.get('GITHUB_REF')=='refs/heads/main' and env.get('GITHUB_EVENT_NAME')=='workflow_dispatch'
        and env.get('GITHUB_RUN_ATTEMPT')=='1' and env.get('CN_REFERENCE_ACK')=='true')
    require(platform.system()=='Darwin' and platform.machine()=='arm64' and platform.mac_ver()[0].split('.')[0]=='15')
    approval=json.loads(env.get('CN_ARM_REFERENCE_APPROVAL','{}'))
    now=int(time.time() if now is None else now)
    require(type(approval) is dict and set(approval)=={'schema','commit','nonce','expires'})
    require(approval['schema']=='cn-arm-reference-approval-v1' and approval['commit']==env.get('GITHUB_SHA')
        and re.fullmatch('[a-f0-9]{40}',approval.get('commit','')) is not None
        and approval.get('nonce')==env.get('CN_REFERENCE_NONCE')
        and re.fullmatch('[a-f0-9]{32}',approval.get('nonce','')) is not None
        and type(approval.get('expires')) is int and now<approval['expires']<=now+1800)
    require(env.get('CN_MODEL_STATE_PRESENT')=='true')
    validate_backup(env)
    reference_run(env)

def reference_run(env):
    run_id=env.get('GITHUB_RUN_ID','');nonce=env.get('CN_REFERENCE_NONCE','')
    require(re.fullmatch('[1-9][0-9]{0,19}',run_id) is not None and re.fullmatch('[a-f0-9]{32}',nonce) is not None)
    title='CN-arm-model-trial-'+nonce
    client=GitHub(env.get('GH_TOKEN',''))
    current=client.call('/actions/runs/'+run_id)
    require(current.get('id')==int(run_id) and current.get('path')==WORKFLOW and current.get('head_branch')=='main'
        and current.get('event')=='workflow_dispatch' and current.get('status')=='in_progress'
        and current.get('head_sha')==env.get('GITHUB_SHA') and current.get('display_title')==title
        and current.get('run_attempt')==1)
    runs=client.call('/actions/workflows/cn-arm-model-bootstrap.yml/runs?event=workflow_dispatch&per_page=100').get('workflow_runs')
    require(type(runs) is list and len(runs)<100 and any(x.get('id')==int(run_id) for x in runs))
    # Failed/cancelled duplicate intents also consume this nonce. A queued run
    # must never authorize another machine after an unknown earlier outcome.
    require(not any(x.get('id')!=int(run_id) and x.get('display_title')==title for x in runs))
