import io
import json
import unittest
import urllib.error
from cn_summary_diagnostic import profile,bodies,trial,CONTEXT_QUERY,client_agents
from store_account_summary import QUERY
import test_cn_session

class CNSummaryDiagnosticContracts(unittest.TestCase):
    def test_private_response_strings_never_escape(self):
        value={'error':{'code':'INTERNAL_SERVER_ERROR','message':'Missing operationName PRIVATE_EMAIL PRIVATE_TOKEN 123456','errorCode':500},'unknown_PRIVATE_FIELD':'PRIVATE_PASSWORD','data':{'email':'PRIVATE_EMAIL'}}
        result=profile(json.dumps(value).encode());text=json.dumps(result)
        self.assertNotIn('PRIVATE',text);self.assertNotIn('123456',text)
        self.assertTrue(result['mentions']['operation']);self.assertTrue(result['mentions']['missing_field'])
        self.assertEqual(result['numeric_errors'],{'errorCode':500})
    def test_body_variants_are_only_the_fixed_readonly_query(self):
        variants=bodies();self.assertEqual([x[0] for x in variants],['account_context','frontend_line_breaks','frontend_escaped_breaks'])
        for _,raw in variants:
            self.assertEqual(' '.join(json.loads(raw)['query'].replace('\\n',' ').split()),CONTEXT_QUERY)
            self.assertNotIn('mutation',raw.decode().lower())
    def test_stops_on_auth_rejection_or_valid_count(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp()
        class Opener:
            def __init__(self,status):self.status=status;self.calls=0
            def open(self,request,timeout):
                self.calls+=1
                raw=json.dumps({'data':{'authorizations':{'authorizedComputers':2}}}).encode()
                return urllib.error.HTTPError(request.full_url,self.status,'PRIVATE_RESPONSE',{},io.BytesIO(raw))
        for status in (200,403,429,307):
            opener=Opener(status);result=trial(fixture.env(),opener)
            self.assertEqual(opener.calls,1);self.assertEqual(result['computer_count_observed'],status==200)
            self.assertNotIn('PRIVATE',json.dumps(result))
    def test_client_identifiers_come_from_bounded_public_versions(self):
        agents=client_agents({'CFBundleShortVersionString':'1.6.2'},'26.2')
        self.assertEqual([x[0] for x in agents],['configurator_legacy','installed_music'])
        self.assertTrue(agents[0][1].startswith('Configurator/2.17 '))
        self.assertEqual(agents[1][1],'Music/1.6.2 (Macintosh; OS X 26.2)')
        for value in ('1.6\r\nX-Private: value','PRIVATE_VALUE','1.6?private=1'):
            with self.assertRaises(ValueError):client_agents({'CFBundleShortVersionString':value},'26.2')
    def test_bounded_classifier_does_not_copy_unstructured_body(self):
        result=profile(b'<html>internal server error PRIVATE_PASSWORD</html>')
        self.assertEqual(result['format'],'html');self.assertTrue(result['mentions']['internal']);self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertEqual(profile(b'x'*65537),{'format':'oversized'})

if __name__=='__main__':unittest.main()
