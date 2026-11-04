import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location("prune_releases",
    Path(__file__).resolve().parents[1]/"deploy/prune_releases.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ReleaseCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.releases=self.root/"releases"
        self.releases.mkdir()
        for char in "abc":
            (self.releases/(char*40)).mkdir()
        (self.root/"current").symlink_to(self.releases/("a"*40))
        (self.root/"previous").symlink_to(self.releases/("b"*40))

    def test_only_old_release_removed_and_unknown_files_retained(self):
        (self.releases/"operator-notes").mkdir()
        (self.root/"state.sqlite3").write_text("private recovery")
        self.assertEqual(module.prune(self.root),1)
        self.assertTrue((self.releases/("a"*40)).is_dir())
        self.assertTrue((self.releases/("b"*40)).is_dir())
        self.assertTrue((self.releases/"operator-notes").is_dir())
        self.assertEqual((self.root/"state.sqlite3").read_text(),"private recovery")
        self.assertEqual(module.prune(self.root),0)

    def test_invalid_previous_link_prevents_all_deletion(self):
        (self.root/"previous").unlink()
        (self.root/"previous").symlink_to(self.root)
        self.assertEqual(module.prune(self.root),0)
        self.assertTrue((self.releases/("c"*40)).is_dir())

    def test_symlink_release_not_followed(self):
        outside=self.root/"outside"
        outside.mkdir()
        (outside/"keep").write_text("keep")
        (self.releases/("d"*40)).symlink_to(outside)
        module.prune(self.root)
        self.assertTrue((outside/"keep").is_file())
        self.assertTrue((self.releases/("d"*40)).is_symlink())

    def test_missing_rollback_prevents_all_deletion(self):
        (self.root/"previous").unlink()
        self.assertEqual(module.prune(self.root),0)

if __name__=="__main__":
    unittest.main()
