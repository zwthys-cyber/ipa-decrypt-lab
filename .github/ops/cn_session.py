"""Load the independent CN session and query a fixed read-only Store endpoint."""
import base64
import json
import os
from pathlib import Path
import re
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
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

def query(env,fetch=None):
    value,session=decode(env)
    pod=value['account'].get('pod')
    require(pod is None or isinstance(pod,str) and re.fullmatch(r'[1-9][0-9]{0,2}',pod) is not None)
    previous=summary.ENDPOINT
    try:
        if pod:summary.ENDPOINT='https://p'+pod+'-buy.itunes.apple.com/account/v1/summary/graphql'
        result=(fetch or fetch_summary)(dict(session,user_agent=summary.UA))
    finally:summary.ENDPOINT=previous
    success=(result.get('status')=='computer_count_observed' and result.get('computer_count_observed') is True
             and result.get('store_session_authenticated') is True and result.get('http_status')==200
             and type(result.get('authorized_computers')) is int and 0<=result['authorized_computers']<=5)
    report={'schema':'cn-session-reuse-v1','status':'session_reused' if success else 'saved_session_query_failed',
            'session_reused':success,'country_bound':'cn','query_client':'legacy_account_summary','pod_route_used':bool(pod),'login_attempted':False,'verification_code_used':False,
            'machine_authorization_attempted':False,'deauthorization_attempted':False,'downloaded':False}
    statuses={'computer_count_observed','apple_request_refused','graphql_errors','http_refused','computer_count_not_returned','response_not_structured','response_shape_unexpected','unexpected_unauthenticated_count','redirect_blocked','response_oversized','transport_failed','query_failed'}
    report['query_status']=result.get('status') if result.get('status') in statuses else 'unknown'
    for key in ('session_cookie_header_present','login_user_agent_preserved','graphql_errors_present','error_mentions_authentication','error_mentions_unknown_field'):
        if type(result.get(key)) is bool:report['query_user_agent_preserved' if key=='login_user_agent_preserved' else key]=result[key]
    for key in ('apple_failure_code','graphql_error_count'):
        if type(result.get(key)) is int and -999999<=result[key]<=999999:report[key]=result[key]
    if success:report['authorized_computers']=result['authorized_computers']
    if type(result.get('http_status')) is int and 100<=result['http_status']<=599:report['http_status']=result['http_status']
    return report

def main():
    os.umask(0o077)
    try:value=query(dict(os.environ))
    except Exception:value={'schema':'cn-session-reuse-v1','status':'saved_session_validation_failed','session_reused':False,'login_attempted':False}
    Path('cn-session-receipt.json').write_text(json.dumps(value));print(json.dumps(value),flush=True)
    return 0 if value.get('session_reused') is True else 2
if __name__=='__main__':raise SystemExit(main())
