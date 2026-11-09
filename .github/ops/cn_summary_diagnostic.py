"""Closed-vocabulary response diagnostics for two fixed read-only CN queries."""
import json
import os
from pathlib import Path
import plistlib
import re
import urllib.error
import urllib.request
from cn_session import decode,require
import store_account_summary as summary

FIELDS={'error','errors','errorCode','errorMessage','code','status','statusCode','message','reason','title','failureType','data','authorizations','authorizedComputers','operationName','query','variables'}
TERMS={
    'authentication':('unauthenticated','unauthorized','authentication','not authenticated','sign in'),
    'forbidden':('forbidden','not permitted','access denied'),
    'expired':('expired','expiration'),
    'request_format':('invalid request','bad request','malformed','deserializ','parse error','parsing'),
    'operation':('operationname','operation name','unknown operation','operation not found'),
    'schema':('cannot query field','unknown field','validation error'),
    'missing_field':('missing','required','not provided','must provide'),
    'method':('method not allowed','unsupported method'),
    'route':('not found','no handler','unknown route'),
    'internal':('internal server error','internalservererror','unexpected error','internal error'),
    'unsupported':('unsupported','not supported','not available'),
    'country':('country','storefront','region'),
    'account_setup':('account setup','account not found','not initialized','terms and conditions','terms of service'),
    'unknown':('unknown error','未知错误','未知錯誤'),
    'retry_later':('try again','try later','稍后再试','稍後再試','稍后重试'),
    'chinese_authentication':('登录','登陆','验证','驗證','密碼','密码'),
    'chinese_account_setup':('条款','條款','尚未使用','未使用过','未使用過'),
    'cookie':('cookie',),'token':('token',),'dsid':('dsid',),
}

def profile(raw):
    if len(raw)>65536:return {'format':'oversized'}
    result={}
    try:value=json.loads(raw);result['format']='json'
    except Exception:
        try:value=plistlib.loads(raw);result['format']='plist'
        except Exception:value=None;result['format']='html' if b'<html' in raw.lower() else 'other'
    result['root_type']={dict:'object',list:'array',str:'string',int:'integer',bool:'boolean',type(None):'null'}.get(type(value),'other')
    messages=[]
    if isinstance(value,dict):
        result['known_fields']={k:{dict:'object',list:'array',str:'string',int:'integer',bool:'boolean',float:'number',type(None):'null'}.get(type(v),'other') for k,v in value.items() if k in FIELDS}
        result['other_fields_bucket']='none' if not set(value)-FIELDS else 'one_to_eight' if len(set(value)-FIELDS)<=8 else 'more'
        numeric={}
        def scan(node,depth=0):
            if depth>4:return
            if isinstance(node,dict):
                for k,v in list(node.items())[:32]:
                    if k in ('errorCode','code','status','statusCode','failureType') and (type(v) is int or isinstance(v,str) and re.fullmatch(r'-?[0-9]{1,5}',v)):
                        number=int(v)
                        if -99999<=number<=99999:numeric[k]=number
                    if k in ('message','errorMessage','reason','title','error','code','errorCode') and isinstance(v,str):messages.append(v[:2048])
                    if k in FIELDS and isinstance(v,(dict,list)):scan(v,depth+1)
            elif isinstance(node,list):
                for v in node[:8]:scan(v,depth+1)
        scan(value)
        if numeric:result['numeric_errors']=numeric
    else:messages.append(raw[:8192].decode(errors='replace'))
    text=' '.join(messages).lower().replace('_',' ')
    result['mentions']={name:any(term in text for term in terms) for name,terms in TERMS.items()}
    return result

# Derived from Apple's public account frontend; request no billing or payment fields.
CONTEXT_QUERY='query requestAccountSummary { account { appleId country } authorizations { authorizedComputers } }'
def bodies():
    multiline='query requestAccountSummary {\n  account { appleId country }\n  authorizations { authorizedComputers }\n}'
    variants=[('account_context',CONTEXT_QUERY),('frontend_line_breaks',multiline),('frontend_escaped_breaks',multiline.replace('\n','\\n'))]
    return [(label,json.dumps({'query':query},separators=(',',':')).encode()) for label,query in variants]

def trial(env,opener=None):
    value,session=decode(env);pod=value['account'].get('pod')
    require(pod is None or isinstance(pod,str) and re.fullmatch(r'[1-9][0-9]{0,2}',pod) is not None)
    url='https://'+('p'+pod+'-buy.itunes.apple.com' if pod else 'buy.itunes.apple.com')+'/account/v1/summary/graphql'
    opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),summary.NoRedirect())
    attempts=[]
    report={'schema':'cn-summary-diagnostic-v1','status':'count_not_observed','computer_count_observed':False,
            'login_attempted':False,'machine_authorization_attempted':False,'deauthorization_attempted':False,'attempts':attempts}
    for label,body in bodies():
        request=summary.make_request(url,session);request.data=body
        try:
            try:response=opener.open(request,timeout=20)
            except urllib.error.HTTPError as error:response=error
            with response:
                raw=response.read(65537);status=response.code
                attempts.append({'variant':label,'http_status':status,'response':profile(raw)})
                if status==200:
                    parsed=summary.parse_response(raw,status,True)
                    if parsed.get('computer_count_observed') is True:
                        report.update(status='computer_count_observed',computer_count_observed=True,authorized_computers=parsed['authorized_computers']);break
                if status in (401,403,429) or 300<=status<=399:break
        except Exception:attempts.append({'variant':label,'status':'transport_failed'});break
    return report

def main():
    os.umask(0o077)
    try:value=trial(dict(os.environ))
    except Exception:value={'schema':'cn-summary-diagnostic-v1','status':'diagnostic_failed','computer_count_observed':False}
    Path('cn-session-receipt.json').write_text(json.dumps(value));print(json.dumps(value),flush=True)
    return 0 if value.get('computer_count_observed') is True else 2
if __name__=='__main__':raise SystemExit(main())
