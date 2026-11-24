"""Synthetic managed controller configuration; no network or real credentials."""
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_daemon import KEYS,credential_mode,service_credentials,require_managed_volume,require_managed_journal
from telegram_queue import QueueError

class ManagedRuntimeTests(unittest.TestCase):
    def test_default_and_invalid_mode(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(credential_mode(),"systemd")
            os.environ["IPAZAKE_CREDENTIAL_MODE"]="invalid"
            with self.assertRaises(QueueError):
                credential_mode()

    def test_managed_credentials_fail_closed(self):
        values={k:"synthetic" for k in KEYS}
        with patch.dict(os.environ,values,clear=True):
            self.assertEqual(service_credentials("environment"),values)
            os.environ["CREDENTIALS_DIRECTORY"]="/tmp/ambiguous"
            with self.assertRaises(QueueError):
                service_credentials("environment")
            del os.environ["CREDENTIALS_DIRECTORY"]
            del os.environ["GH_TOKEN"]
            with self.assertRaises(QueueError):
                service_credentials("environment")

    def test_volume_must_be_private_and_mounted(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            row="11 10 0:42 / "+str(root.resolve())+" rw - ext4 /dev/example rw"
            require_managed_volume(root,row)
            with self.assertRaises(QueueError):
                require_managed_volume(root,"")
            root.chmod(0o755)
            with self.assertRaises(QueueError):
                require_managed_volume(root,row)

    def test_tf_state_requires_migration(self):
        class Journal: pass
        journal=Journal()
        with sqlite3.connect(":memory:") as journal.db:
            journal.db.execute("CREATE TABLE tasks(rid TEXT)")
            journal.db.execute("INSERT INTO tasks VALUES (?)",("cn_"+"a"*32,))
            require_managed_journal(journal)
            journal.db.execute("INSERT INTO tasks VALUES (?)",("tf_"+"b"*32,))
            with self.assertRaises(QueueError):
                require_managed_journal(journal)
        journal.db.close()

if __name__=="__main__":
    unittest.main()
