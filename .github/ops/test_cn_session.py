import base64
import copy
import io
import json
import time
import unittest
from contextlib import redirect_stdout
from cn_session import CNSessionError,decode,query
from store_account_summary import make_request,BODY
import store_account_summary as summary

class CNSavedSessionContracts(unittest.TestCase):
    def setUp(self):
        self.value={'schema':'cn-account-session-v1','email':'cn@example.invalid','guid':'001122AABBCC','store':'143465','created':100,
            'account':{'email':'cn@example.invalid','store':'143465','password':'PRIVATE_PASSWORD','passwordToken':'PRIVATE_TOKEN',
                'directoryServicesIdentifier':'123','labStoreFront':'143465-19,32','cookie':[]}}
        self.settings={'GITHUB_ACTIONS':'true','APPLE_CN_ID':'CN@example.invalid','APPLE_CN_GUID':'001122aabbcc'}
    def env(self,value=None):
        return dict(self.settings,APPLE_CN_SESSION_B64=base64.b64encode(json.dumps(value or self.value).encode()).decode())
    def test_readonly_query_reuses_token_without_password_or_login(self):
        def fetch(session):
            request=make_request('https://buy.itunes.apple.com/account/v1/summary/graphql',session)
            self.assertEqual(request.data,BODY);self.assertEqual(request.get_header('X-token'),'PRIVATE_TOKEN')
            self.assertNotIn('PRIVATE_PASSWORD',str(request.headers));self.assertEqual(session['guid'],'001122AABBCC')
            return {'status':'computer_count_observed','computer_count_observed':True,'store_session_authenticated':True,'http_status':200,'authorized_computers':2}
        capture=io.StringIO()
        with redirect_stdout(capture):result=query(self.env(),fetch)
        self.assertTrue(result['session_reused']);self.assertFalse(result['login_attempted']);self.assertEqual(capture.getvalue(),'')
        for secret in ('PRIVATE_TOKEN','PRIVATE_PASSWORD','cn@example.invalid'):self.assertNotIn(secret,json.dumps(result))
    def test_rejects_foreign_account_country_guid_and_future_envelope(self):
        for section,key,value in [(None,'guid','000000000000'),(None,'store','143443'),(None,'email','de@example.invalid'),(None,'created',10**12),('account','email','de@example.invalid'),('account','store','143443'),('account','labStoreFront','143443-1')]:
            changed=copy.deepcopy(self.value)
            (changed if section is None else changed[section])[key]=value
            with self.assertRaises(CNSessionError):decode(self.env(changed),now=200)
    def test_invalid_inputs_never_reach_network(self):
        for encoded in ('','not-base64','A'*45001,base64.b64encode(b'[]').decode()):
            def reject(_):self.fail('invalid session reached network')
            with self.assertRaises(CNSessionError):query(dict(self.settings,APPLE_CN_SESSION_B64=encoded),reject)
        with self.assertRaises(CNSessionError):decode(dict(self.env(),GITHUB_ACTIONS='false'))
    def test_pod_is_apple_only_and_global_endpoint_is_restored(self):
        original=summary.ENDPOINT;changed=copy.deepcopy(self.value);changed['account']['pod']='71'
        def fetch(session):
            self.assertEqual(summary.ENDPOINT,'https://p71-buy.itunes.apple.com/account/v1/summary/graphql')
            request=make_request(summary.ENDPOINT,session)
            self.assertEqual(request.host,'p71-buy.itunes.apple.com')
            return {'status':'http_refused','http_status':500}
        result=query(self.env(changed),fetch)
        self.assertTrue(result['pod_route_used']);self.assertEqual(summary.ENDPOINT,original)
        for pod in ('71.evil.invalid','71:443','71/..','0001',True):
            changed['account']['pod']=pod
            with self.assertRaises(CNSessionError):query(self.env(changed),lambda _:self.fail('unsafe pod reached network'))
        self.assertEqual(summary.ENDPOINT,original)
    def test_refused_saved_token_does_not_trigger_login_or_expose_response(self):
        result=query(self.env(),lambda _:{'status':'PRIVATE_SERVER_MESSAGE','http_status':403,'password':'PRIVATE_PASSWORD'})
        self.assertFalse(result['session_reused']);self.assertFalse(result['login_attempted'])
        self.assertNotIn('PRIVATE',json.dumps(result));self.assertEqual(result['http_status'],403)

if __name__=='__main__':unittest.main()
