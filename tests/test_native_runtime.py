import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_runtime import BINARIES, RESOURCE, SCHEMA, WORKFLOW, fingerprint, unpack, trusted_run

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.archive = self.root / "runtime.tar.gz"
        self.destination = self.root / "runtime"
        self.files = {name: b"synthetic executable" for name in BINARIES}
        self.files[RESOURCE + "/test.txt"] = b"synthetic resource"
        self.manifest = dict(schema=SCHEMA, fingerprint="a"*64, pool="macos-26-intel",
            commit="b"*40, run_id="123", files={name:dict(size=len(data),
            sha256=hashlib.sha256(data).hexdigest()) for name, data in self.files.items()})

    def write(self, extra=None):
        with tarfile.open(self.archive, "w:gz") as output:
            for name, raw in {"manifest.json":json.dumps(self.manifest).encode(), **self.files}.items():
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                output.addfile(info, io.BytesIO(raw))
            if extra:
                output.addfile(extra)

    def extract(self, **kwargs):
        return unpack(self.archive, self.destination, "a"*64, "macos-26-intel", **kwargs)

    def test_valid_and_executable(self):
        self.write()
        self.extract(commit="b"*40, run_id=123)
        self.assertEqual((self.destination / "ApplePackageTool").stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.destination / RESOURCE / "test.txt").read_bytes(), b"synthetic resource")

    def test_wrong_source_platform_and_provenance(self):
        for key, value in (("fingerprint","c"*64),("pool","macos-15-intel"),("commit","c"*40),("run_id","999")):
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = value
                self.write()
                with self.assertRaises(ValueError):
                    self.extract(commit="b"*40,run_id=123)
                self.assertFalse(self.destination.exists())
                self.manifest[key] = original

    def test_tampered_bytes_cleaned(self):
        self.files["ApplePackageTool"] = b"x"*len(self.files["ApplePackageTool"])
        self.write()
        with self.assertRaisesRegex(ValueError, "digest_mismatch"):
            self.extract()
        self.assertFalse(self.destination.exists())

    def test_traversal_symlink_duplicate_and_oversize(self):
        for name, kind, size in (("../escape",tarfile.REGTYPE,0),
                                  ("ApplePackageTool",tarfile.SYMTYPE,0),
                                  ("ApplePackageTool",tarfile.REGTYPE,0),
                                  ("licenses/huge",tarfile.REGTYPE,600*1024*1024)):
            with self.subTest(name=name, kind=kind, size=size):
                info=tarfile.TarInfo(name)
                info.type,info.size,info.linkname=kind,size,"/etc/passwd"
                self.write(info)
                with self.assertRaises((ValueError,tarfile.TarError)):
                    self.extract()
                self.assertFalse(self.destination.exists())

    def test_missing_binary(self):
        del self.files["delivery-crypt"]
        del self.manifest["files"]["delivery-crypt"]
        self.write()
        with self.assertRaisesRegex(ValueError,"inventory"):
            self.extract()

    def test_producer_must_be_successful_main_build(self):
        artifact={"workflow_run":{"id":123,"head_sha":"b"*40}}
        run=dict(id=123,head_sha="b"*40,path=WORKFLOW,head_branch="main",
                 event="push",status="completed",conclusion="success")
        self.assertTrue(trusted_run(run,artifact))
        for key,value in (("path","other.yml"),("event","pull_request"),("head_branch","feature"),
                          ("conclusion","failure"),("status","in_progress"),("head_sha","c"*40)):
            self.assertFalse(trusted_run(dict(run,**{key:value}),artifact))

    def test_fingerprint_ignores_bytecode_but_tracks_sources(self):
        (self.root / WORKFLOW).parent.mkdir(parents=True)
        (self.root / WORKFLOW).write_text("build")
        (self.root / "tools").mkdir()
        source=self.root / "tools/tool.py"
        source.write_text("one")
        first=fingerprint(self.root)
        (self.root / "tools/__pycache__").mkdir()
        (self.root / "tools/__pycache__/tool.pyc").write_bytes(b"ignored")
        self.assertEqual(fingerprint(self.root),first)
        source.write_text("two")
        self.assertNotEqual(fingerprint(self.root),first)

if __name__ == "__main__":
    unittest.main()
