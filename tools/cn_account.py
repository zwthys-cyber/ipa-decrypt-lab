"""Load the independent CN session and query a fixed read-only Store endpoint."""
import base64
import json
import os
from pathlib import Path
import re
import time
from store_account_summary import validate_session,fetch_summary
import store_account_summary as summary

UA='Configurator/2.21 (Macintosh; OS X 15.2; 24C5089c) AppleWebKit/0620.1.16.11.6'

class CNSessionError(ValueError):pass

def require(value):
    if not value:raise CNSessionError('cn_session_invalid')

def decode(env,now=None):
    require(env.get('GITHUB_ACTIONS')=='true')
    encoded=env.get('APPLE_CN_SESSION_B64','')
    require(isinstance(encoded,str) and 0<len(encoded)<=45000)
    try:raw=base64.b64decode(encoded,validate=True)
    except Exception:raise CNSessionError('cn_session_invalid') from None
    require(0<len(raw)<=32768)
    try:value=json.loads(raw)
    except Exception:raise CNSessionError('cn_session_invalid') from None
    require(isinstance(value,dict) and set(value)=={'schema','email','guid','store','created','account'})
    email=env.get('APPLE_CN_ID','').strip();guid=env.get('APPLE_CN_GUID','').upper()
    require(bool(email) and re.fullmatch(r'[A-F0-9]{12}',guid) is not None)
    require(value['schema']=='cn-account-session-v1' and value['store']=='143465'
            and isinstance(value['email'],str) and value['email'].casefold()==email.casefold()
            and value['guid']==guid and type(value['created']) is int and 0<value['created']<=int(time.time() if now is None else now)+60)
    account=value['account']
    require(isinstance(account,dict) and isinstance(account.get('email'),str)
            and account['email'].casefold()==email.casefold() and account.get('store')=='143465')
    front=account.get('labStoreFront') or '143465-1'
    require(isinstance(front,str) and front.startswith('143465-'))
    try:
        session=validate_session({'dsid':account.get('directoryServicesIdentifier'),'guid':guid,
            'token':account.get('passwordToken'),'user_agent':UA,'storefront':front,'cookies':account.get('cookie')})
    except Exception:raise CNSessionError('cn_session_invalid') from None
    return value,session
