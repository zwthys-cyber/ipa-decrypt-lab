import errno
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fairplay_state_observer as observer


class StateTests(unittest.TestCase):
    def test_metadata_distinguishes_missing_denied_empty_and_nonempty(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "private.sidb"
            self.assertEqual(observer.metadata(path)["status"], "missing")
            path.touch()
            self.assertEqual(observer.metadata(path)["status"], "regular_empty")
            path.write_bytes(b"PRIVATE_SYNTHETIC")
            self.assertEqual(observer.metadata(path)["status"], "regular_nonempty")
        with patch.object(observer.os, "lstat", side_effect=PermissionError(errno.EACCES, "PRIVATE_SYNTHETIC")):
            self.assertEqual(observer.metadata("ignored")["status"], "permission_denied")

    def test_symlink_is_not_treated_as_state_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path/"source").write_bytes(b"PRIVATE_SYNTHETIC")
            (path/"state.sidb").symlink_to(path/"source")
            self.assertEqual(observer.metadata(path/"state.sidb")["status"], "symlink")
            self.assertEqual(observer.inventory(path)["sidb_files"], 0)

    def test_inventory_reports_counts_without_names_or_contents(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path/"PRIVATE_SYNTHETIC.sidb").write_bytes(b"PRIVATE_SYNTHETIC")
            (path/"empty.sids").touch()
            (path/"ignored.txt").write_text("PRIVATE_SYNTHETIC")
            result = observer.inventory(path)
        self.assertEqual(result["sidb_files"], 1)
        self.assertEqual(result["nonempty_sidb"], 1)
        self.assertEqual(result["sids_files"], 1)
        self.assertEqual(result["nonempty_sids"], 0)
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(result))

    def test_inventory_has_entry_and_time_bounds(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            for i in range(4):
                (path/str(i)).touch()
            self.assertTrue(observer.inventory(path, max_entries=2)["limit_reached"])
            self.assertTrue(observer.inventory(path, max_seconds=0)["limit_reached"])

    def test_inventory_does_not_follow_directory_symlinks(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path/"data").mkdir()
            (path/"data"/"file.sidb").write_text("PRIVATE")
            (path/"data"/"loop").symlink_to(path)
            result = observer.inventory(path)
        self.assertEqual(result["sidb_files"], 1)
        self.assertFalse(result["limit_reached"])

    def test_clean_removes_unknown_fields(self):
        value = dict(schema="ipa-lab-fairplay-state-v1", running_as_root=True,
                     file_contents_read=False, account_request_attempted=False,
                     files={name:dict(status="missing", path="PRIVATE_SYNTHETIC") for name in observer.PATHS},
                     inventory={}, private="PRIVATE_SYNTHETIC")
        self.assertNotIn("PRIVATE_SYNTHETIC", json.dumps(observer.clean(value)))

    def test_clean_rejects_invalid_status_and_claimed_content_read(self):
        value = dict(schema="ipa-lab-fairplay-state-v1", running_as_root=True,
                     file_contents_read=False, account_request_attempted=False,
                     files={name:dict(status="missing") for name in observer.PATHS}, inventory={})
        value["file_contents_read"] = True
        with self.assertRaises(ValueError):
            observer.clean(value)
        value["file_contents_read"] = False
        value["files"]["shared_sidb"]["status"] = "PRIVATE_SYNTHETIC"
        with self.assertRaises(ValueError):
            observer.clean(value)


if __name__ == "__main__":
    unittest.main()
