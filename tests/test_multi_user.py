"""Real SQLite tenant boundaries; Telegram/GitHub side effects are synthetic."""
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from multi_user import MultiUserService, actor
from persistent_journal import PersistentJournal
from telegram_daemon import ServerController, process_update
from telegram_queue import QueueError

ADMIN=123456789
ALICE=123456701
BOB=123456702
APP="333903271"
RID="a"*32
OTHER="b"*32

def update(uid,text,number=1):
    return {"update_id":number,"message":{"date":int(time.time()),"text":text,
        "from":{"id":uid,"is_bot":False},"chat":{"id":uid,"type":"private"}}}

def callback(uid,chat=None):
    return {"update_id":99,"callback_query":{"id":"callback-id","data":"menu:help",
        "from":{"id":uid,"is_bot":False},"message":{"message_id":7,
        "from":{"id":999999,"is_bot":True},"chat":{"id":uid if chat is None else chat,"type":"private"}}}}

class MultiUserContracts(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.path=Path(self.directory.name)/"state.sqlite3"
        self.environment=patch.dict(os.environ,{"TMPDIR":self.directory.name});self.environment.start()
        self.bot=Mock();self.bot.message.return_value={"message_id":7}
        self.gh=Mock();self.gh.dispatch.return_value={"status":"queued"};self.gh.find.return_value=None
        self.menu=patch('multi_user.configure',return_value={});self.menu.start()
        self.journal=PersistentJournal(self.path,ADMIN)
        self.service=MultiUserService(self.bot,self.gh,ADMIN,"crypt","synthetic",self.journal,20,ServerController)
        self.number=10
    def tearDown(self):
        self.service.close();self.journal.close();self.menu.stop();self.environment.stop();self.directory.cleanup()
    def send(self,uid,text):
        self.number+=1;item=update(uid,text,self.number);process_update(self.service,self.journal,item);return item
    def grant(self,uid=ALICE,limit=3):self.send(ADMIN,"/allow "+str(uid)+" "+str(limit))
    def restart(self):
        self.service.close();self.journal.close()
        self.journal=PersistentJournal(self.path,ADMIN)
        self.service=MultiUserService(self.bot,self.gh,ADMIN,"crypt","synthetic",self.journal,20,ServerController)

    def test_default_is_admin_only_and_onboarding_shares_only_own_id(self):
        self.send(ALICE,"/start");self.send(ALICE,"/start");self.send(ALICE,APP)
        self.assertEqual(self.bot.message.call_count,1)
        self.assertEqual(self.bot.message.call_args.args[0],ALICE)
        self.assertIn(str(ALICE),self.bot.message.call_args.args[1])
        self.assertNotIn(str(ADMIN),self.bot.message.call_args.args[1])
        self.assertEqual(set(self.service.controllers),{ADMIN})
        self.gh.dispatch.assert_not_called();self.gh.preflight_app.assert_not_called()

    def test_only_admin_can_manage_allowlist_and_it_survives_restart(self):
        self.grant();self.send(ALICE,"/allow "+str(BOB))
        self.assertNotIn(BOB,self.service.enabled)
        self.restart();self.assertIn(ALICE,self.service.enabled)
        self.assertEqual(self.service.tenant(ALICE).submission_limit,3)
        self.send(ADMIN,"/deny "+str(ADMIN))
        self.assertIn(ADMIN,self.service.enabled)
        self.send(ADMIN,"/allow "+str(BOB)+" 999")
        self.assertNotIn(BOB,self.service.enabled)

    def test_group_messages_and_forged_private_callbacks_cannot_route(self):
        forged=update(ADMIN,"/allow "+str(ALICE));forged['message']['chat']={'id':ADMIN,'type':'group'}
        self.service.handle(forged);self.assertNotIn(ALICE,self.service.enabled)
        self.grant();self.bot.reset_mock()
        self.service.handle(callback(ALICE,ADMIN))
        self.service.handle(dict(callback(ALICE),update_id=True))
        self.bot.call.assert_not_called();self.gh.dispatch.assert_not_called()
        self.assertIsNone(actor(callback(ALICE,ADMIN)))

    def test_get_and_backend_reject_foreign_tasks_before_network_access(self):
        self.grant();self.grant(BOB)
        a,b=self.service.tenant(ALICE),self.service.tenant(BOB)
        a.journal.write(RID,"delivered",APP)
        self.send(BOB,"/get "+RID)
        self.gh.find.assert_not_called();self.gh.deliver.assert_not_called()
        for operation in (lambda:b.github.find(RID),lambda:b.github.runs(RID),lambda:b.github.cancel(RID),
                          lambda:b.github.retry(APP,RID,1),lambda:b.github.deliver(RID,self.bot,BOB,"crypt")):
            with self.assertRaises(QueueError):operation()
        b.journal.write(OTHER,"closed",APP)
        with self.assertRaises(QueueError):b.github.deliver(OTHER,self.bot,ALICE,"crypt")
        self.gh.cancel.assert_not_called();self.gh.retry.assert_not_called();self.gh.deliver.assert_not_called()
        self.send(ADMIN,"/get "+RID);self.gh.deliver.assert_not_called()

    def test_own_get_delivers_only_to_owner_and_replay_is_not_sent_twice(self):
        self.grant();c=self.service.tenant(ALICE);c.journal.write(RID,"closed",APP)
        def deliver(*args,**kwargs):
            self.assertEqual(args[2],ALICE);kwargs['progress']('uploading')
            return {'status':'telegram_file_delivered','request_id':RID,'bytes':100}
        self.gh.deliver.side_effect=deliver
        with patch('telegram_daemon.shutil.disk_usage',return_value=Mock(free=10**12)):
            item=self.send(ALICE,"/get "+RID)
            process_update(self.service,self.journal,item)
        self.gh.deliver.assert_called_once()
        self.assertEqual(c.journal.records[RID]['state'],'delivered')
        self.assertNotIn(RID,self.journal.records)
        self.assertEqual(self.journal.offset(),item['update_id']+1)

    def test_other_users_active_export_blocks_dispatch_before_intent(self):
        self.grant();self.grant(BOB)
        self.send(ALICE,APP)
        self.assertEqual(self.gh.dispatch.call_count,1)
        a=self.service.tenant(ALICE);rid=a.current['rid']
        self.send(BOB,APP)
        self.assertEqual(self.gh.dispatch.call_count,1)
        self.assertEqual(self.service.tenant(BOB).journal.records,{})
        self.assertEqual(self.service.access.submissions(),1)
        self.assertIn(rid,a.journal.records)
        self.assertNotIn(str(ALICE),self.bot.message.call_args.args[1])

    def test_per_user_and_global_quotas_are_separate_and_utc_bounded(self):
        self.grant(limit=1);self.grant(BOB)
        a=self.service.tenant(ALICE);a.journal.write(RID,"closed",APP)
        self.send(ALICE,APP);self.gh.dispatch.assert_not_called()
        self.send(BOB,APP);self.assertEqual(self.gh.dispatch.call_count,1)
        b=self.service.tenant(BOB);b.current=None
        for i in range(18):self.journal.write(format(i+10,'032x'),"closed",APP)
        self.assertEqual(self.service.access.submissions(),20)
        self.assertFalse(self.service.admit(BOB,"export"))
        self.send(BOB,APP);self.assertEqual(self.gh.dispatch.call_count,1)
        tomorrow=(int(time.time())//86400+1)*86400
        with patch('multi_user.time.time',return_value=tomorrow):self.assertEqual(self.service.access.submissions(),0)

    def test_cached_lists_remain_private_and_live_queries_share_admission(self):
        self.grant();self.grant(BOB)
        a,b=self.service.tenant(ALICE),self.service.tenant(BOB)
        a.journal.write(RID,"pending",APP);a.current={'rid':RID,'app':APP}
        entry={'at':int(time.time()),'used_at':int(time.time()),'rows':[{'id':'864000001','version':'12.41','date':'2026-11-08'}],'total':1,'next_before':''}
        b.browser.state['cache'][APP]=entry
        self.bot.call.side_effect=lambda method,payload,**kwargs:{'message_id':11,'chat':{'id':payload.get('chat_id')}}
        self.send(BOB,"/versions "+APP)
        self.assertEqual(b.browser.state['view']['app'],APP)
        self.assertIsNone(b.browser.state['pending'])
        b.browser.start(APP,77)
        self.assertIsNone(b.browser.state['pending'])
        self.gh.call.assert_not_called()
        self.assertNotIn(APP,a.browser.state['cache'])

    def test_catalog_query_budget_is_global_and_does_not_reset_on_regrant(self):
        self.grant();self.grant(BOB)
        a,b=self.service.tenant(ALICE),self.service.tenant(BOB)
        a.browser.state['queries']=[int(time.time())]*20;a.browser.save()
        self.assertFalse(self.service.admit(BOB,'catalog'))
        self.send(ADMIN,"/deny "+str(ALICE));self.grant()
        self.assertEqual(self.service.access.queries(),20)
        self.assertFalse(self.service.admit(BOB,'catalog'))
        self.assertEqual(b.browser.state['queries'],[])

    def test_revocation_is_durable_blocks_delivery_and_waits_for_cancel_confirmation(self):
        self.grant();c=self.service.tenant(ALICE)
        c.journal.write(RID,"pending",APP);c.current={'rid':RID,'app':APP}
        self.send(ADMIN,"/deny "+str(ALICE))
        self.assertNotIn(ALICE,self.service.enabled);self.assertEqual(len(self.service.retired),1)
        self.gh.cancel.assert_called_once_with(RID)
        with PersistentJournalContext(self.path,ALICE) as ledger:self.assertEqual(ledger.records[RID]['state'],'cancelled')
        self.restart();self.service.recover();self.gh.deliver.assert_not_called()
        self.gh.find.return_value={'status':'in_progress'};self.service.tick()
        self.assertFalse(self.service.admit(ADMIN,'export'))
        self.gh.find.return_value={'status':'completed','conclusion':'cancelled'};self.service.tick()
        self.assertEqual(self.service.retired,[])
        self.grant();self.assertIsNone(self.service.tenant(ALICE).current)
        self.gh.deliver.assert_not_called()

    def test_user_cancel_also_preserves_global_drain_after_unknown_transport(self):
        self.grant();c=self.service.tenant(ALICE)
        c.journal.write(RID,"pending",APP);c.current={'rid':RID,'app':APP}
        self.gh.cancel.side_effect=QueueError('github_transport_unknown')
        self.send(ALICE,'/cancel')
        self.assertIsNone(c.current);self.assertTrue(self.service.retired)
        self.assertEqual(c.journal.records[RID]['state'],'cancelled')
        self.assertFalse(self.service.admit(ADMIN,'export'))
        self.restart();self.assertTrue(self.service.retired)

    def test_recovery_uses_old_admin_namespace_and_never_replays_guest_sends(self):
        self.journal.write(RID,'delivered',APP)
        self.grant();a=self.service.tenant(ALICE);a.journal.write(OTHER,'sending',APP)
        self.restart();self.service.recover()
        self.assertEqual(self.service.tenant(ADMIN).journal.scope,self.journal.scope)
        self.assertIn(RID,self.service.tenant(ADMIN).delivered)
        self.gh.deliver.assert_not_called();self.gh.dispatch.assert_not_called()
        notices=[call.args[0] for call in self.bot.message.call_args_list if '上次文件发送结果需要确认' in call.args[1]]
        self.assertEqual(notices,[ALICE])

    def test_atomic_cancel_intent_prevents_auto_delivery_after_interruption(self):
        self.grant();c=self.service.tenant(ALICE)
        c.journal.write(RID,"pending",APP);c.current={'rid':RID,'app':APP}
        self.service.retire(ALICE,"export",RID,APP)
        self.gh.find.return_value={'status':'completed','conclusion':'success'}
        self.service.tick()
        self.assertIsNone(c.current)
        self.assertEqual(c.journal.records[RID]['state'],'cancelled')
        self.gh.deliver.assert_not_called()

    def test_catalog_cancel_is_atomic_and_cannot_retire_other_users_work(self):
        self.grant();self.grant(BOB);c=self.service.tenant(ALICE)
        c.browser.state['pending']={'rid':RID,'app':APP,'at':int(time.time())};c.browser.save()
        with self.assertRaises(QueueError):self.service.retire(BOB,"catalog",RID,APP)
        self.service.retire(ALICE,"catalog",RID,APP)
        self.assertIsNone(c.browser.state['pending'])
        self.assertIsNone(c.journal.browser_load()['pending'])
        self.assertEqual(len(self.service.retired),1)
        self.restart();self.service.recover()
        self.assertIsNone(self.service.tenant(ALICE).browser.state['pending'])
        self.gh.deliver.assert_not_called();self.gh.dispatch.assert_not_called()

    def test_claimed_update_and_failed_acl_write_cannot_grant_access(self):
        with patch.object(self.service.access,'grant',side_effect=sqlite3.OperationalError('synthetic')):
            with self.assertRaises(sqlite3.OperationalError):self.send(ADMIN,'/allow '+str(ALICE))
        self.assertNotIn(ALICE,self.service.enabled)
        self.restart();self.assertNotIn(ALICE,self.service.enabled)

class PersistentJournalContext:
    def __init__(self,path,owner):self.journal=PersistentJournal(path,owner)
    def __enter__(self):return self.journal
    def __exit__(self,*args):self.journal.close()

if __name__=='__main__':unittest.main()
