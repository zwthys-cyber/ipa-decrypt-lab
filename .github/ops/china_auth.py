"""Isolated GitHub-only CN authentication probe. No fallback or account artifacts."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from native_store import classify, run

class ChinaAuthError(ValueError):pass

def settings(env):
    if env.get('GITHUB_ACTIONS')!='true':raise ChinaAuthError('requires_github_actions')
    email=env.get('APPLE_CN_ID','').strip()
    password=env.get('APPLE_CN_PASSWORD','')
    if not email or not password:raise ChinaAuthError('china_credentials_missing')
    if len(email)>320 or len(password)>4096 or any(c in email for c in '\r\n') or '\x00' in password:
        raise ChinaAuthError('china_credentials_invalid')
    legacy=env.get('LEGACY_APPLE_ID','').strip()
    if not legacy:raise ChinaAuthError('legacy_identity_comparison_missing')
    if email.casefold()==legacy.casefold():raise ChinaAuthError('same_account_not_allowed')
    guid=env.get('APPLE_CN_GUID','')
    if not re.fullmatch(r'[0-9A-Fa-f]{12}',guid):raise ChinaAuthError('china_guid_missing_or_invalid')
    code=env.get('APPLE_CN_2FA_CODE','').strip()
    if code and not re.fullmatch(r'[0-9]{6}',code):raise ChinaAuthError('china_verification_code_invalid')
    return email,password,guid.upper(),code

def probe(binary,env,execute=None):
    email,password,guid,code=settings(env)
    home=Path(env['HOME'])
    folder=home/'.ipatool'/hashlib.md5(email.lower().encode()).hexdigest()
    if folder.exists() or folder.is_symlink():raise ChinaAuthError('china_account_cache_not_empty')
    args=['login',email,'--guid',guid]
    if code:args+=['--code',code]
    child={key:env[key] for key in ('HOME','PATH','LANG') if key in env}
    child['APPLEPACKAGE_PASSWORD']=password
    execute=execute or run
    try:
        try:result=execute(binary,args,child,timeout=120)
        except subprocess.TimeoutExpired:return {'schema':'ipa-cn-auth-v1','status':'authentication_timeout','authenticated':False}
        state=classify(result)
        if state!='authenticated':
            return {'schema':'ipa-cn-auth-v1','status':state,'authenticated':False,'verification_code_supplied':bool(code)}
        path=folder/'account.json'
        if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024 or path.stat().st_mode&0o077:
            raise ChinaAuthError('private_account_cache_invalid')
        account=json.loads(path.read_bytes())
        if (not isinstance(account,dict) or not isinstance(account.get('email'),str)
                or account['email'].casefold()!=email.casefold() or not account.get('passwordToken')
                or not account.get('directoryServicesIdentifier')):raise ChinaAuthError('china_account_binding_invalid')
        if account.get('store')!='143465':raise ChinaAuthError('china_storefront_mismatch')
        return {'schema':'ipa-cn-auth-v1','status':'authenticated_cn','authenticated':True,
                'country_verified':'cn','verification_code_supplied':bool(code),'session_retained':False}
    finally:
        # Only the newly created CN email namespace is removed; no legacy login/logout.
        if folder.exists() and not folder.is_symlink():shutil.rmtree(folder)

def main():
    os.umask(0o077)
    try:value=probe(str(Path(sys.argv[1]).resolve()),dict(os.environ))
    except ChinaAuthError as exc:value={'schema':'ipa-cn-auth-v1','status':str(exc),'authenticated':False}
    except Exception:value={'schema':'ipa-cn-auth-v1','status':'china_auth_probe_failed','authenticated':False}
    print(json.dumps(value),flush=True)
    return 0 if value.get('authenticated') is True else 2
if __name__=='__main__':raise SystemExit(main())
