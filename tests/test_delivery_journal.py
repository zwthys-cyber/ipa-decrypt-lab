import copy
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from delivery_journal import Journal, ANCHOR
from telegram_queue import QueueError
from telegram_session import Controller, opaque_id
from test_telegram_session import update, OWNER

RID="a"*32

class Checks:
    def __init__(self):
        self.items=[]
        self.fail=False
    def call(self,path,payload=None,method="GET"):
        if self.fail:
            raise QueueError("github_transport_unknown")
        if method=="POST":
            item=copy.deepcopy(payload)
            item.update(id=len(self.items)+1,app={"slug":"github-actions"})
            self.items.append(item)
            return item
        if path.startswith("/check-runs/"):
            return self.items[int(path.rsplit("/",1)[1])-1]
        return {"check_runs":list(self.items)}

class JournalTests(unittest.TestCase):
    def test_new_process_recovers_latest_state(self):
        api=Checks()
        j=Journal(api,"synthetic",OWNER)
        j.write(RID,"pending","6599842047")
        j.write(RID,"sending")
        j.write(RID,"delivered")
        fresh=Journal(api,"synthetic",OWNER)
        fresh.load()
        self.assertEqual(fresh.records[RID]["state"],"delivered")
        self.assertEqual(fresh.records[RID]["app"],"6599842047")
        self.assertEqual(fresh.pending(),[])

    def test_other_owner_cannot_read_journal(self):
        api=Checks()
        Journal(api,"synthetic",OWNER).write(RID,"pending","6599842047")
        j=Journal(api,"synthetic",OWNER+1)
        self.assertEqual(j.load(),{})

    def test_forged_state_or_wrong_check_binding_rejected(self):
        for field in ("signature","app","head","external"):
            api=Checks()
            Journal(api,"synthetic",OWNER).write(RID,"pending")
            item=api.items[0]
            if field=="signature":
                e=json.loads(item["output"]["summary"])
                e["record"]["state"]="delivered"
                item["output"]["summary"]=json.dumps(e)
            elif field=="app":
                item["app"]["slug"]="other-app"
            elif field=="head":
                item["head_sha"]="f"*40
            else:
                item["external_id"]="b"*32
            self.assertEqual(Journal(api,"synthetic",OWNER).load(),{})

    def test_public_payload_has_no_owner_or_token(self):
        api=Checks()
        Journal(api,"private-token-value",OWNER).write(RID,"pending")
        raw=json.dumps(api.items)
        self.assertNotIn(str(OWNER),raw)
        self.assertNotIn("private-token-value",raw)

    def test_write_failure_prevents_dispatch(self):
        api=Checks()
        j=Journal(api,"synthetic",OWNER)
        api.fail=True
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=j)
        with self.assertRaises(QueueError):
            c.handle(update())
        gh.dispatch.assert_not_called()

    def test_write_failure_prevents_send(self):
        api=Checks()
        j=Journal(api,"synthetic",OWNER)
        api.fail=True
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=j)
        self.assertFalse(c.deliver(RID))
        gh.deliver.assert_not_called()

    def test_restart_tracks_without_dispatch_or_retry(self):
        api=Checks()
        Journal(api,"synthetic",OWNER).write(RID,"pending","6599842047")
        bot,gh=Mock(),Mock()
        gh.find.return_value={"id":5,"status":"in_progress"}
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        c.recover()
        self.assertEqual(c.current["rid"],RID)
        self.assertFalse(c.failover({"id":5}))
        gh.dispatch.assert_not_called()
        gh.retry.assert_not_called()

    def test_unknown_send_is_not_repeated_after_restart(self):
        api=Checks()
        Journal(api,"synthetic",OWNER).write(RID,"sending")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        c.recover()
        self.assertIsNone(c.current)
        gh.deliver.assert_not_called()

    def test_completed_delivery_is_not_repeated_after_restart(self):
        api=Checks()
        Journal(api,"synthetic",OWNER).write(RID,"delivered")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        c.recover()
        c.resume(RID)
        gh.deliver.assert_not_called()
        self.assertIn(RID,c.delivered)

    def test_replayed_update_is_not_dispatched(self):
        api=Checks()
        rid=opaque_id("synthetic",OWNER,1,"6599842047")
        Journal(api,"synthetic",OWNER).write(rid,"closed","6599842047")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        c.recover()
        c.handle(update())
        gh.dispatch.assert_not_called()

    def test_ack_then_journal_failure_does_not_resend_after_restart(self):
        api=Checks()
        journal=Journal(api,"synthetic",OWNER)
        bot,gh=Mock(),Mock()
        def delivered(*args,**kwargs):
            api.fail=True
            return {"status":"telegram_file_delivered","request_id":RID,"bytes":100}
        gh.deliver.side_effect=delivered
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal)
        c.deliver(RID)
        self.assertEqual(api.items[-1]["external_id"],RID)
        api.fail=False
        fresh_gh=Mock()
        fresh=Controller(bot,fresh_gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        fresh.recover()
        fresh_gh.deliver.assert_not_called()
        self.assertEqual(fresh.journal.records[RID]["state"],"sending")

    def test_cancel_api_failure_prevents_auto_delivery_after_restart(self):
        api=Checks()
        journal=Journal(api,"synthetic",OWNER)
        journal.write(RID,"pending","6599842047")
        bot,gh=Mock(),Mock()
        gh.cancel.side_effect=QueueError("github_transport_unknown")
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal)
        c.current={"rid":RID,"app":"6599842047"}
        with self.assertRaises(QueueError):
            c.handle(update(text="/cancel"))
        self.assertIsNone(c.current)
        fresh=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        fresh.recover()
        gh.deliver.assert_not_called()

    def test_expired_or_future_pending_is_not_auto_recovered(self):
        j=Journal(Checks(),"synthetic",OWNER)
        for at in (int(time.time())-86401,int(time.time())+3600):
            j.records={RID:{"state":"pending","at":at}}
            self.assertEqual(j.pending(),[])

    def test_saturated_history_fails_closed(self):
        api=Mock()
        api.call.return_value={"check_runs":[{}]*100}
        with self.assertRaises(QueueError):
            Journal(api,"synthetic",OWNER).load()
        self.assertEqual(api.call.call_count,5)

    def test_multiple_pending_do_not_start_parallel_delivery(self):
        api=Checks()
        j=Journal(api,"synthetic",OWNER)
        j.write(RID,"pending","6599842047")
        j.write("b"*32,"pending","1530340312")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=Journal(api,"synthetic",OWNER))
        with self.assertRaises(QueueError):
            c.recover()
        gh.deliver.assert_not_called()

if __name__=="__main__":
    unittest.main()
