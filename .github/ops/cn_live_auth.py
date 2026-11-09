"""Keep one native login process alive; deliver a fresh encrypted code to stdin."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
from china_auth import settings,ChinaAuthError,failure_diagnostic
from cn_protocol import GitHub,poll_code,require
from cn_session import decode as decode_saved_session
from telegram_queue import QueueError

MARKER=b'IPA_CN_AUTH:verification_pending'

def live(binary,crypt,env,relay=None,command=None,window=300,poll_interval=3,prepared_session=False,native_guid=None):
    saved=None
    if prepared_session:
        saved,_=decode_saved_session(env)
        email=saved['email'];password=saved['account']['password'];guid=native_guid or saved['guid']
        require(isinstance(guid,str) and re.fullmatch(r'[A-F0-9]{12}',guid),'invalid_prepared_guid')
    else:
        require(native_guid is None,'unexpected_native_guid')
        email,password,guid,_=settings(env)
    folder=Path(env['HOME'])/'.ipatool'/hashlib.md5(email.lower().encode()).hexdigest()
    if prepared_session:
        path=folder/'account.json'
        require(not folder.is_symlink() and path.is_file() and not path.is_symlink() and path.stat().st_mode&0o077==0 and 0<path.stat().st_size<=32768,'prepared_cn_cache_invalid')
        existing=json.loads(path.read_bytes())
        require(existing==saved['account'],'prepared_cn_cache_binding')
    elif folder.exists() or folder.is_symlink():raise ChinaAuthError('china_account_cache_not_empty')
    child_env={key:env[key] for key in ('HOME','PATH','LANG') if key in env}
    if not prepared_session:child_env['APPLEPACKAGE_PASSWORD']=password
    args=command or [binary,'resume-cn' if prepared_session else 'login-cn',email,'--guid',guid]
    process=subprocess.Popen(args,env=child_env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    selector=selectors.DefaultSelector();selector.register(process.stdout,selectors.EVENT_READ,'stdout');selector.register(process.stderr,selectors.EVENT_READ,'stderr')
    capture={'stdout':bytearray(),'stderr':bytearray()};partial=bytearray();waiting=None;submitted=False;next_poll=0
    transient_reads=0
    deadline=time.monotonic()+180
    try:
        while selector.get_map():
            if time.monotonic()>deadline:raise ChinaAuthError('verification_window_expired' if waiting else 'authentication_timeout')
            for key,_ in selector.select(0.2):
                chunk=os.read(key.fd,65536)
                if not chunk:selector.unregister(key.fileobj);continue
                capture[key.data].extend(chunk)
                if len(capture[key.data])>1024*1024:del capture[key.data][:-1024*1024]
                if key.data!='stdout':continue
                partial.extend(chunk)
                while b'\n' in partial:
                    line,_,rest=partial.partition(b'\n');partial[:]=rest
                    if line.rstrip(b'\r')==MARKER and waiting is None:
                        waiting={'schema':'cn-live-request-v1','auth_run':env['GITHUB_RUN_ID'],'commit':env['GITHUB_SHA'],
                                 'nonce':secrets.token_hex(16),'expires':int(time.time())+window}
                        path=Path(env['CN_HANDSHAKE_FILE']);temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(waiting));temporary.chmod(0o600);os.replace(temporary,path)
                        deadline=time.monotonic()+window
                        print('{"schema":"ipa-cn-auth-live-v1","stage":"waiting_for_live_code"}',flush=True)
                if len(partial)>8192:partial.clear()
            if waiting and not submitted and time.monotonic()>=next_poll:
                next_poll=time.monotonic()+poll_interval
                try:
                    if relay is None:
                        api=GitHub(env['GH_TOKEN']);code=poll_code(api,waiting,crypt,env['DELIVERY_AGE_IDENTITY'])
                    else:code=relay(waiting)
                    transient_reads=0
                except QueueError as error:
                    if str(error) not in {'github_transport_unknown','github_request_rejected'} or transient_reads>=6:raise
                    transient_reads+=1;next_poll=time.monotonic()+min(2**transient_reads,10)
                    print(json.dumps({'schema':'ipa-cn-auth-live-v1','stage':'waiting_for_live_code','relay_read_retry':transient_reads}),flush=True)
                    code=None
                if code is not None:
                    require(isinstance(code,str) and re.fullmatch(r'[0-9]{6}',code),'invalid_live_code')
                    process.stdin.write(code.encode()+b'\n');process.stdin.flush();process.stdin.close();submitted=True
                    deadline=time.monotonic()+120
        process.wait(timeout=max(0.1,deadline-time.monotonic()))
        if process.returncode!=0:
            result=subprocess.CompletedProcess([],process.returncode,capture['stdout'].decode(errors='replace'),capture['stderr'].decode(errors='replace'))
            return {'schema':'ipa-cn-auth-live-v1','status':'native_login_rejected','authenticated':False,'verification_submitted':submitted,'diagnostic':failure_diagnostic(result)},None
        path=folder/'account.json'
        require(path.is_file() and not path.is_symlink() and path.stat().st_size<=32768 and path.stat().st_mode&0o077==0,'private_cn_session_invalid')
        account=json.loads(path.read_bytes())
        require(isinstance(account,dict) and str(account.get('email','')).casefold()==email.casefold()
                and account.get('store')=='143465' and bool(account.get('passwordToken')) and bool(account.get('directoryServicesIdentifier')),'cn_session_binding')
        envelope={'schema':'cn-account-session-v1','email':email,'guid':guid,'store':'143465','created':int(time.time()),'account':account}
        return {'schema':'ipa-cn-auth-live-v1','status':'authenticated_cn','authenticated':True,'country_verified':'cn','verification_submitted':submitted},envelope
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=1)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        selector.close()
        for stream in (process.stdin,process.stdout,process.stderr):
            try:stream.close()
            except OSError:pass
        if not prepared_session and folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

def seal_session(sealer,envelope,env):
    with tempfile.TemporaryDirectory(prefix='cn-session-private-') as directory:
        path=Path(directory)/'session.json';path.write_text(json.dumps(envelope,separators=(',',':')));path.chmod(0o600)
        child={k:env[k] for k in ('HOME','PATH','LANG') if k in env};child['GITHUB_ACTIONS']='true'
        completed=subprocess.run([sealer,str(path)],env=child,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
        require(completed.returncode==0 and len(completed.stdout)<=65536,'cn_session_sealing_failed')
        value=json.loads(completed.stdout)
        require(value.get('schema')=='ipa-cn-session-secret-v1' and value.get('secret_name')=='APPLE_CN_SESSION_B64'
                and value.get('repository')=='zwthys-cyber/ipa-decrypt-lab' and value.get('key_id')=='3380204578043523366'
                and isinstance(value.get('encrypted_value'),str),'cn_sealed_session_binding')
        value.update(auth_run=env['GITHUB_RUN_ID'],commit=env['GITHUB_SHA'])
        Path('cn-session-secret-relay.json').write_text(json.dumps(value))

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--crypt',required=True);p.add_argument('--sealer',required=True);args=p.parse_args()
    def stop(*_):raise InterruptedError()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        env=dict(os.environ)
        value,envelope=live(str(Path(args.binary).resolve()),str(Path(args.crypt).resolve()),env)
        if envelope is not None:
            seal_session(str(Path(args.sealer).resolve()),envelope,env)
            value['session_secret_prepared']=True
    except ChinaAuthError as exc:value={'schema':'ipa-cn-auth-live-v1','status':str(exc),'authenticated':False}
    except Exception:value={'schema':'ipa-cn-auth-live-v1','status':'live_cn_auth_failed','authenticated':False}
    Path('cn-auth-receipt.json').write_text(json.dumps(value));print(json.dumps(value),flush=True)
    return 0 if value.get('authenticated') is True and value.get('session_secret_prepared') is True else 2
if __name__=='__main__':raise SystemExit(main())
