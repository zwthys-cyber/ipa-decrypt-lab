"""Controller recovery contracts backed by the production SQLite journal."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from persistent_journal import PersistentJournal
from telegram_queue import QueueError
from telegram_controller import Controller, opaque_id
from test_telegram_controller import update, OWNER

RID="a"*32

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/"state.sqlite3"
        self.connections=[]
        self.fail=False

    def journal(self):
        journal=PersistentJournal(self.path,OWNER)
        original=journal.write
        def write(*args,**kwargs):
            if self.fail:
                raise QueueError("journal_write_failed")
            return original(*args,**kwargs)
        journal.write=write
        self.connections.append(journal)
        return journal

    def tearDown(self):
        for journal in self.connections:
            journal.close()
        self.directory.cleanup()

    def test_write_failure_prevents_dispatch(self):
        j=self.journal()
        self.fail=True
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=j)
        with self.assertRaises(QueueError):
            c.handle(update())
        gh.dispatch.assert_not_called()

    def test_write_failure_prevents_send(self):
        j=self.journal()
        self.fail=True
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=j)
        self.assertFalse(c.deliver(RID))
        gh.deliver.assert_not_called()

    def test_restart_tracks_without_dispatch_or_retry(self):
        self.journal().write(RID,"pending","6599842047")
        bot,gh=Mock(),Mock()
        gh.find.return_value={"id":5,"status":"in_progress"}
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        c.recover()
        self.assertEqual(c.current["rid"],RID)
        self.assertFalse(c.failover({"id":5}))
        gh.dispatch.assert_not_called()
        gh.retry.assert_not_called()

    def test_unknown_send_is_not_repeated_after_restart(self):
        self.journal().write(RID,"sending")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        c.recover()
        self.assertIsNone(c.current)
        gh.deliver.assert_not_called()

    def test_completed_delivery_is_not_repeated_after_restart(self):
        self.journal().write(RID,"delivered")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        c.recover()
        c.resume(RID)
        gh.deliver.assert_not_called()
        self.assertIn(RID,c.delivered)

    def test_replayed_update_is_not_dispatched(self):
        rid=opaque_id("synthetic",OWNER,1,"6599842047")
        self.journal().write(rid,"closed","6599842047")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        c.recover()
        c.handle(update())
        gh.dispatch.assert_not_called()

    def test_ack_then_journal_failure_does_not_resend_after_restart(self):
        journal=self.journal()
        bot,gh=Mock(),Mock()
        def delivered(*args,**kwargs):
            kwargs["progress"]("uploading")
            self.fail=True
            return {"status":"telegram_file_delivered","request_id":RID,"bytes":100}
        gh.deliver.side_effect=delivered
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal)
        c.deliver(RID)
        self.assertEqual(journal.records[RID]["state"],"sending")
        self.fail=False
        fresh_gh=Mock()
        fresh=Controller(bot,fresh_gh,OWNER,"crypt","synthetic",journal=self.journal())
        fresh.recover()
        fresh_gh.deliver.assert_not_called()
        self.assertEqual(fresh.journal.records[RID]["state"],"sending")

    def test_cancel_api_failure_prevents_auto_delivery_after_restart(self):
        journal=self.journal()
        journal.write(RID,"pending","6599842047")
        bot,gh=Mock(),Mock()
        gh.cancel.side_effect=QueueError("github_transport_unknown")
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=journal)
        c.current={"rid":RID,"app":"6599842047"}
        with self.assertRaises(QueueError):
            c.handle(update(text="/cancel"))
        self.assertIsNone(c.current)
        fresh=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        fresh.recover()
        gh.deliver.assert_not_called()

    def test_multiple_pending_do_not_start_parallel_delivery(self):
        j=self.journal()
        j.write(RID,"pending","6599842047")
        j.write("b"*32,"pending","1530340312")
        bot,gh=Mock(),Mock()
        c=Controller(bot,gh,OWNER,"crypt","synthetic",journal=self.journal())
        with self.assertRaises(QueueError):
            c.recover()
        gh.deliver.assert_not_called()


if __name__=="__main__":
    unittest.main()
