import copy
import json
from pathlib import Path
import tempfile
import unittest
from cn_model import gate,payload,account_at,CNModelError,COMMERCE_READY,base
import test_cn_session

class CNModelBoundaries(unittest.TestCase):
    def setUp(self):
        fixture=test_cn_session.CNSavedSessionContracts();fixture.setUp();self.value=fixture.value
        self.count={'session_reused':True,'http_status':200,'authorized_computers':0}
        self.prepared=dict({k:True for k in COMMERCE_READY},status='commerce_request_prepared',authorization_request_attempted=False,running_as_root=False)
    def test_quota_unknown_full_boolean_or_refused_never_passes_authorization_gate(self):
        for key,value in [('authorized_computers',5),('authorized_computers',True),('authorized_computers',None),('session_reused',False),('http_status',500)]:
            count=dict(self.count);count[key]=value
            with self.assertRaises(CNModelError):gate(count,{'ready':True},self.prepared,{'root_status':'observed'})
        gate(self.count,{'ready':True},self.prepared,{'root_status':'observed'})
    def test_unverified_binding_or_input_cannot_consume_machine_slot(self):
        for key in COMMERCE_READY:
            prepared=dict(self.prepared);prepared[key]=False
            with self.assertRaises(CNModelError):gate(self.count,{'ready':True},prepared,{'root_status':'observed'})
        with self.assertRaises(CNModelError):gate(self.count,{'ready':False},self.prepared,{'root_status':'observed'})
        with self.assertRaises(CNModelError):gate(self.count,{'ready':True},self.prepared,{'root_status':'unavailable'})
    def test_payload_rejects_cross_account_and_never_includes_password(self):
        result=payload(self.value,self.value['account'],'001122AABBCC')
        self.assertNotIn('password',result);self.assertNotIn('PRIVATE_PASSWORD',json.dumps(result))
        for key,value in [('store','143443'),('email','other@example.invalid'),('directoryServicesIdentifier','999')]:
            account=copy.deepcopy(self.value['account']);account[key]=value
            with self.assertRaises(CNModelError):payload(self.value,account,'001122AABBCC')
    def test_private_cache_identity_permissions_and_symlinks_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'account.json';path.write_text(json.dumps(self.value['account']));path.chmod(0o600)
            self.assertEqual(account_at(path,self.value)['store'],'143465')
            path.chmod(0o644)
            with self.assertRaises(CNModelError):account_at(path,self.value)
            path.chmod(0o600);link=Path(directory)/'alias';link.symlink_to(path)
            with self.assertRaises(CNModelError):account_at(link,self.value)
    def test_initial_report_never_claims_model_or_authorization_success(self):
        result=base()
        for key in ('authorization_request_attempted','model_recovered','decryption_proven','plaintext_verified','checkpoint_saved','model_secret_prepared'):
            self.assertIs(result[key],False)

if __name__=='__main__':unittest.main()
