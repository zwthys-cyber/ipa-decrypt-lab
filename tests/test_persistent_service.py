import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from persistent_journal import PersistentJournal
from telegram_daemon import process_update, load_credentials, heartbeat, backup, KEYS
from telegram_queue import QueueError, GitHub
from telegram_api import APIError

RID="a"*32
OWNER=123456789

class PersistentTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.root=Path(self.directory.name)
        self.path=self.root/"state.sqlite3"
        self.journal=PersistentJournal(self.path,OWNER)
    def tearDown(self):
        self.journal.close()
        self.directory.cleanup()

    def test_pending_survives_new_connection(self):
        self.journal.write(RID,"pending","6599842047")
        fresh=PersistentJournal(self.path,OWNER)
        try:
            self.assertEqual(fresh.pending()[0]["rid"],RID)
            self.assertEqual(fresh.records[RID]["app"],"6599842047")
        finally:
            fresh.close()

    def test_terminal_state_keeps_creation_and_app(self):
        self.journal.write(RID,"pending","6599842047")
        created=self.journal.records[RID]["created"]
        self.journal.write(RID,"sending")
        self.journal.write(RID,"delivered")
        self.assertEqual(self.journal.records[RID]["created"],created)
        self.assertEqual(self.journal.records[RID]["app"],"6599842047")
        self.assertEqual(self.journal.pending(),[])
        self.assertEqual(self.journal.daily_submissions(),1)

    def test_uncertain_send_not_pending_after_restart(self):
        self.journal.write(RID,"sending")
        fresh=PersistentJournal(self.path,OWNER)
        try:
            self.assertEqual(fresh.pending(),[])
            self.assertEqual(fresh.records[RID]["state"],"sending")
        finally:
            fresh.close()

    def test_owner_scope_isolation(self):
        self.journal.write(RID,"pending")
        fresh=PersistentJournal(self.path,OWNER+1)
        try:
            self.assertEqual(fresh.records,{})
            self.assertEqual(fresh.daily_submissions(),0)
        finally:
            fresh.close()

    def test_invalid_transition_input_does_not_write(self):
        with self.assertRaises(QueueError):
            self.journal.write(RID,"bogus")
        with self.assertRaises(QueueError):
            self.journal.write("invalid","pending")
        with self.assertRaises(QueueError):
            self.journal.write(RID,"pending","123;secret")
        self.assertEqual(self.journal.records,{})

    def test_database_permissions_private(self):
        self.assertEqual(self.path.stat().st_mode & 0o077,0)
        other=self.root/"public.sqlite3"
        other.touch(mode=0o644)
        os.chmod(other,0o644)
        with self.assertRaises(QueueError):
            PersistentJournal(other,OWNER)

    def test_symlink_database_rejected(self):
        link=self.root/"link.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            PersistentJournal(link,OWNER)

    def test_daily_count_utc_boundary(self):
        with patch("persistent_journal.time.time",return_value=86400*100+86399):
            self.journal.write(RID,"closed")
        self.assertEqual(self.journal.daily_submissions(86400*100+86400),0)
        self.assertEqual(self.journal.daily_submissions(86400*100+86399),1)

    def test_update_processed_once(self):
        controller=Mock()
        update={"update_id":7}
        process_update(controller,self.journal,update)
        process_update(controller,self.journal,update)
        controller.handle.assert_called_once_with(update)
        self.assertEqual(self.journal.offset(),8)

    def test_crash_after_claim_does_not_replay_send(self):
        self.assertTrue(self.journal.claim_update(7))
        controller=Mock()
        fresh=PersistentJournal(self.path,OWNER)
        try:
            process_update(controller,fresh,{"update_id":7})
            controller.handle.assert_not_called()
            self.assertEqual(fresh.offset(),8)
        finally:
            fresh.close()

    def test_unknown_effect_result_is_not_replayed(self):
        for error in (APIError("telegram_transport_unknown"),QueueError("github_transport_unknown")):
            controller=Mock()
            controller.handle.side_effect=error
            uid=10+self.journal.offset()
            process_update(controller,self.journal,{"update_id":uid})
            process_update(controller,self.journal,{"update_id":uid})
            controller.handle.assert_called_once()

    def test_corrupt_update_does_not_call_controller(self):
        controller=Mock()
        for update in (None,{},{"update_id":True},{"update_id":-1}):
            process_update(controller,self.journal,update)
        controller.handle.assert_not_called()

    def test_claim_before_side_effect(self):
        controller=Mock()
        def handle(update):
            self.assertFalse(self.journal.claim_update(update["update_id"]))
        controller.handle.side_effect=handle
        process_update(controller,self.journal,{"update_id":42})

    def test_database_write_failure_prevents_side_effect(self):
        controller=Mock()
        with patch.object(self.journal,"claim_update",side_effect=sqlite3.OperationalError("synthetic")):
            with self.assertRaises(sqlite3.OperationalError):
                process_update(controller,self.journal,{"update_id":8})
        controller.handle.assert_not_called()

    def test_optional_checks_permission_is_not_required(self):
        api=GitHub("synthetic")
        api.call=Mock(side_effect=QueueError("github_permission_denied"))
        self.assertIsNone(api.read_checks("/check-runs/123"))
        self.assertFalse(api.checks_readable)
        self.assertIsNone(api.read_checks("/check-runs/124"))
        api.call.assert_called_once()

    def test_missing_checks_never_confirms_queue_cancellation(self):
        api=GitHub("synthetic")
        api.checks_readable=False
        self.assertFalse(api.queued_confirmed({"head_sha":"f"*40},[{"id":123}]))

    def test_missing_checks_uses_actions_steps(self):
        api=GitHub("synthetic")
        api.checks_readable=False
        api.jobs=Mock(return_value=[{"id":123,"status":"in_progress","steps":[]}])
        self.assertEqual(api.progress({"id":123,"head_sha":"f"*40},RID),"preparing")

    def test_backup_can_restore_state(self):
        self.journal.write(RID,"delivered","6599842047")
        backup(self.journal,self.root)
        fresh=PersistentJournal(self.root/"recovery-backup.sqlite3",OWNER)
        try:
            self.assertEqual(fresh.records[RID]["state"],"delivered")
        finally:
            fresh.close()

    def test_health_has_no_identifying_task_data(self):
        path=self.root/"health.json"
        heartbeat(path,"ready",{"rid":RID,"app":"6599842047"})
        value=json.loads(path.read_text())
        self.assertTrue(value["task_active"])
        self.assertNotIn(RID,path.read_text())
        self.assertNotIn("6599842047",path.read_text())

    def test_credentials_schema_and_private_mode(self):
        path=self.root/"credentials.json"
        path.write_text(json.dumps({k:"synthetic-value" for k in KEYS}))
        path.chmod(0o600)
        self.assertEqual(set(load_credentials(path)),KEYS)
        path.chmod(0o644)
        with self.assertRaises(QueueError):
            load_credentials(path)

    def test_credentials_extra_keys_and_newlines_rejected(self):
        path=self.root/"credentials.json"
        for value in ({**{k:"x" for k in KEYS},"APPLE_PASSWORD":"not-allowed"},
                      {k:"x\ny" for k in KEYS}):
            path.write_text(json.dumps(value))
            path.chmod(0o600)
            with self.assertRaises(QueueError):
                load_credentials(path)

if __name__=="__main__":
    unittest.main()
