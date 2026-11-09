import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import hashlib
spec=importlib.util.spec_from_file_location('inspection',Path(__file__).with_name('access_inspect.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class InspectionContracts(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.root=Path(self.directory.name)
        self.admin=123456789;self.guest=123456701;self.nonce='a'*32;self.rid='b'*32
        for folder in ['etc/ipazake','opt/ipazake/current','var/lib/ipazake']:(self.root/folder).mkdir(parents=True,exist_ok=True)
        config=self.root/'etc/ipazake/bot.json';config.write_text(json.dumps({'TELEGRAM_OWNER_ID':str(self.admin),'TELEGRAM_BOT_TOKEN':'PRIVATE_TOKEN'}));config.chmod(0o600)
        (self.root/'opt/ipazake/current/SOURCE_COMMIT').write_text(module.SOURCE)
        (self.root/'var/lib/ipazake/health.json').write_text(json.dumps({'state':'ready','task_active':False}))
        db=sqlite3.connect(self.root/'var/lib/ipazake/state.sqlite3')
        db.executescript('CREATE TABLE tenant_access(namespace TEXT,uid INTEGER,enabled INTEGER,daily_limit INTEGER);CREATE TABLE tasks(scope TEXT,rid TEXT,state TEXT);CREATE TABLE metadata(scope TEXT,name TEXT,value TEXT);')
        scope=lambda uid:hashlib.sha256(('telegram-owner:'+str(uid)).encode()).hexdigest()
        db.execute('INSERT INTO tenant_access VALUES(?,?,1,3)',(scope(self.admin),self.guest))
        db.execute('INSERT INTO tasks VALUES(?,?,?)',(scope(self.guest),self.rid,'delivered'))
        db.execute('INSERT INTO metadata VALUES(?,?,?)',(scope(self.guest),'progress:'+self.rid,json.dumps({'stage':'done','finished':123.0,'message_id':77})))
        db.commit();db.close()
        self.request={'uid':self.guest,'admin':self.admin,'nonce':self.nonce,'expires':1100,'expected_request':self.rid}
    def tearDown(self):self.directory.cleanup()
    def run_inspect(self,**values):return module.inspect(self.root,dict(self.request,**values),self.nonce,now=1000)
    def test_guest_ownership_and_sanitized_output(self):
        value=self.run_inspect();self.assertTrue(value['target_authorized']);self.assertTrue(value['expected_request_owned'])
        self.assertEqual(value['expected_request_state'],'delivered');self.assertEqual(value['target_daily_limit'],3)
        self.assertTrue(value['separate_from_administrator']);self.assertEqual(value['expected_progress_stage'],'done')
        self.assertTrue(value['expected_progress_finished']);self.assertTrue(value['expected_progress_message_saved'])
        text=json.dumps(value)
        for secret in [str(self.guest),str(self.admin),self.rid,'PRIVATE_TOKEN']:self.assertNotIn(secret,text)
    def test_admin_is_identified_without_confusing_guest_receipt(self):
        value=self.run_inspect(uid=self.admin);self.assertTrue(value['target_is_administrator']);self.assertFalse(value['expected_request_owned'])
    def test_unknown_user_has_no_access_or_other_users_record(self):
        value=self.run_inspect(uid=123456702);self.assertFalse(value['target_authorized']);self.assertFalse(value['expected_request_owned'])
        self.assertIsNone(value['expected_progress_stage']);self.assertFalse(value['expected_progress_message_saved'])
    def test_invalid_or_expired_requests_are_rejected(self):
        for values in [{'uid':True},{'expires':999},{'expires':3000},{'nonce':'c'*32},{'expected_request':'bad'}]:
            with self.assertRaises(ValueError):self.run_inspect(**values)
    def test_mismatched_admin_or_unverified_source_is_rejected(self):
        with self.assertRaises(ValueError):self.run_inspect(admin=123456702)
        (self.root/'opt/ipazake/current/SOURCE_COMMIT').write_text('c'*40)
        with self.assertRaises(ValueError):self.run_inspect()
if __name__=='__main__':unittest.main()
