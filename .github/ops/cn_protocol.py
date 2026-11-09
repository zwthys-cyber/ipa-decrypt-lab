"""Nonce/source-bound live code relay. Public artifacts contain no plaintext code."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from telegram_queue import GitHub, require, sha256

AUTH='.github/workflows/china-account-auth.yml'
RELAY='.github/workflows/china-otp-relay.yml'

def request(value,run,commit,nonce=None,now=None):
    now=int(time.time() if now is None else now)
    require(isinstance(value,dict) and set(value)=={'schema','auth_run','commit','nonce','expires'},'invalid_cn_request')
    require(value['schema']=='cn-live-request-v1' and value['auth_run']==str(run) and value['commit']==commit,'cn_request_binding')
    require(re.fullmatch(r'[a-f0-9]{40}',commit or '') and re.fullmatch(r'[1-9][0-9]{0,19}',str(run)),'cn_identity')
    require(isinstance(value['nonce'],str) and re.fullmatch(r'[a-f0-9]{32}',value['nonce']),'cn_nonce')
    require(nonce is None or value['nonce']==nonce,'cn_nonce_binding')
    require(type(value['expires']) is int and now<value['expires']<=now+300,'cn_request_expired')
    return dict(value)

def code_payload(value,waiting,now=None):
    now=int(time.time() if now is None else now)
    request(waiting,waiting['auth_run'],waiting['commit'],now=now)
    require(isinstance(value,dict) and set(value)=={'schema','auth_run','commit','nonce','issued_at','code'},'invalid_cn_code_payload')
    require(value['schema']=='cn-live-code-v1' and all(value[k]==waiting[k] for k in ('auth_run','commit','nonce')),'cn_code_binding')
    require(type(value['issued_at']) is int and 0<=now-value['issued_at']<=180,'cn_code_expired')
    require(isinstance(value['code'],str) and re.fullmatch(r'[0-9]{6}',value['code']),'cn_code_format')
    return value['code']

def artifact_bytes(api,item,member,max_bytes=32768):
    require(item.get('expired') is False and type(item.get('id')) is int and type(item.get('size_in_bytes')) is int and 0<item['size_in_bytes']<=max_bytes,'cn_artifact_bounds')
    require(isinstance(item.get('digest'),str) and re.fullmatch(r'sha256:[a-f0-9]{64}',item['digest']),'cn_artifact_digest')
    with tempfile.TemporaryDirectory(prefix='cn-relay-artifact-') as directory:
        path=Path(directory)/'artifact.zip';api.archive(item['id'],path,max_bytes=max_bytes)
        require('sha256:'+sha256(path)==item['digest'],'cn_artifact_digest')
        with zipfile.ZipFile(path) as z:
            entries=z.infolist()
            require(len(entries)==1 and entries[0].filename==member and not entries[0].is_dir() and 0<entries[0].file_size<=8192 and not entries[0].flag_bits&1,'cn_artifact_inventory')
            return z.read(entries[0])

def waiting_request(api,run_id,nonce,commit):
    require(isinstance(run_id,str) and re.fullmatch(r'[1-9][0-9]{0,19}',run_id) and isinstance(nonce,str) and re.fullmatch(r'[a-f0-9]{32}',nonce) and re.fullmatch(r'[a-f0-9]{40}',commit or ''),'invalid_cn_identity')
    run=api.call('/actions/runs/'+str(run_id))
    trusted_titles={AUTH:{'China-account-authenticate'},'.github/workflows/china-model-bootstrap.yml':{'CN-model-trial','CN-model-replay'},'.github/workflows/china-relay-probe.yml':{'CN-relay-synthetic-probe'},'.github/workflows/cn-arm-model-bootstrap.yml':{'CN-arm-model-trial','CN-arm-model-replay'}}
    require(run.get('path') in trusted_titles and run.get('head_branch')=='main' and run.get('event')=='workflow_dispatch'
            and run.get('display_title') in trusted_titles[run['path']] and run.get('status')=='in_progress' and run.get('head_sha')==commit,'cn_auth_session_not_waiting')
    name='cn-auth-request-'+str(run_id)+'-'+nonce
    items=api.call('/actions/runs/'+str(run_id)+'/artifacts?per_page=100').get('artifacts',[])
    found=[x for x in items if x.get('name')==name]
    require(len(found)==1,'cn_request_artifact_missing')
    raw=artifact_bytes(api,found[0],'request.json')
    require(len(raw)<=2048,'cn_request_size')
    return request(json.loads(raw),run_id,commit,nonce)

def encrypt_payload(crypt,output,payload,recipient,execute=None):
    execute=execute or subprocess.run
    with tempfile.TemporaryDirectory(prefix='cn-code-private-') as directory:
        root=Path(directory);root.chmod(0o700);plain=root/'code.json'
        plain.write_text(json.dumps(payload));plain.chmod(0o600)
        env={key:os.environ[key] for key in ('HOME','PATH','LANG') if key in os.environ};env['GITHUB_ACTIONS']='true'
        result=execute([crypt,'encrypt',str(plain),str(output),recipient],env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
        require(result.returncode==0 and output.is_file() and 0<output.stat().st_size<=8192,'cn_code_encryption_failed')

def decrypt_code(crypt,sealed,waiting,identity,execute=None):
    execute=execute or subprocess.run
    require(isinstance(sealed,bytes) and 0<len(sealed)<=8192,'cn_code_ciphertext_size')
    with tempfile.TemporaryDirectory(prefix='cn-code-private-') as directory:
        root=Path(directory);root.chmod(0o700);cipher=root/'code.age';plain=root/'code.json'
        cipher.write_bytes(sealed);cipher.chmod(0o600)
        env={key:os.environ[key] for key in ('HOME','PATH','LANG') if key in os.environ}
        env.update(GITHUB_ACTIONS='true',DELIVERY_AGE_IDENTITY=identity)
        result=execute([crypt,'decrypt',str(cipher),str(plain)],env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=30)
        require(result.returncode==0 and plain.is_file() and 0<plain.stat().st_size<=2048,'cn_code_decryption_failed')
        return code_payload(json.loads(plain.read_bytes()),waiting)

def poll_code(api,waiting,crypt,identity):
    data=api.call('/actions/workflows/china-otp-relay.yml/runs?event=workflow_dispatch&per_page=20')
    title='CN-code-relay-'+waiting['auth_run']+'-'+waiting['nonce']
    for run in data.get('workflow_runs',[]):
        if not (run.get('path')==RELAY and run.get('head_branch')=='main' and run.get('event')=='workflow_dispatch'
                and run.get('display_title')==title and run.get('head_sha')==waiting['commit']
                and run.get('status')=='completed' and run.get('conclusion')=='success'):continue
        name='cn-code-'+waiting['auth_run']+'-'+waiting['nonce']
        items=api.call('/actions/runs/'+str(run['id'])+'/artifacts?per_page=100').get('artifacts',[])
        found=[x for x in items if x.get('name')==name]
        if not found:continue
        require(len(found)==1,'cn_duplicate_code_artifact')
        return decrypt_code(crypt,artifact_bytes(api,found[0],'code.age'),waiting,identity)
    return None
