import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("circle_runtime", Path(__file__).with_name("runtime.py"))
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)

class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.expected = dict(commit="a"*40, workflow_id="12345678-1234-1234-1234-123456789abc",
                             job_number="7", source_fingerprint="b"*64, xcode="Xcode 26.5",
                             swift="Swift 6", macos="26.3.1", variant="base", dependencies="")
        self.payloads = {name: b"public fixture" for name in runtime.BINARIES}
        self.payloads[runtime.RESOURCE + "/fixture.txt"] = b"resource"
        self.manifest = dict(schema=runtime.SCHEMA, platform="circleci-macos-26-arm64",
                             **self.expected)
        self.manifest["files"] = {n: dict(size=len(v), sha256=hashlib.sha256(v).hexdigest())
                                  for n, v in self.payloads.items()}

    def archive(self, extra=None, changed=None):
        path = self.root / "runtime.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            values = dict(self.payloads)
            if changed:
                values.update(changed)
            values["manifest.json"] = json.dumps(self.manifest).encode()
            for name, data in values.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            if extra:
                archive.addfile(extra)
        return path

    def verify(self, **kwargs):
        return runtime.unpack(self.archive(**kwargs), self.root / "out", self.expected)

    def test_valid_fixture_and_permissions(self):
        result = self.verify()
        self.assertEqual(result["job_number"], "7")
        self.assertEqual((self.root / "out/ApplePackageTool").stat().st_mode & 0o777, 0o755)
        self.assertEqual((self.root / "out" / runtime.RESOURCE / "fixture.txt").read_bytes(), b"resource")

    def test_digest_mismatch_removes_output(self):
        with self.assertRaisesRegex(ValueError, "digest_mismatch"):
            self.verify(changed={"ApplePackageTool": b"x"*len(b"public fixture")})
        self.assertFalse((self.root / "out").exists())

    def test_wrong_platform_and_circle_identity(self):
        for key, value in (("platform", "macos-26-intel"), ("workflow_id", "87654321-1234-1234-1234-123456789abc"),
                           ("commit", "c"*40), ("xcode", "Xcode 26.2"), ("job_number", "8"), ("variant", "cn"), ("dependencies", "different ABI")):
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = value
                with self.assertRaises(ValueError):
                    self.verify()
                self.manifest[key] = original

    def test_path_escape(self):
        info = tarfile.TarInfo("../escape")
        with self.assertRaisesRegex(ValueError, "invalid_path"):
            self.verify(extra=info)
        self.assertFalse((self.root / "escape").exists())

    def test_duplicate_and_link(self):
        for link in (False, True):
            info = tarfile.TarInfo("ApplePackageTool")
            if link:
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
            with self.assertRaises(ValueError):
                self.verify(extra=info)

    def test_missing_binary_and_unknown_payload(self):
        del self.payloads["lab-kbsync"]
        del self.manifest["files"]["lab-kbsync"]
        with self.assertRaisesRegex(ValueError, "inventory_mismatch"):
            self.verify()
        self.payloads["credentials.txt"] = b"refuse"
        with self.assertRaisesRegex(ValueError, "invalid_path"):
            self.verify()

    def test_partial_expected_identity_rejected(self):
        del self.expected["xcode"]
        with self.assertRaisesRegex(ValueError, "trusted_identity_required"):
            self.verify()

    def test_cn_archive_has_separate_profile(self):
        self.expected["variant"] = self.manifest["variant"] = "cn"
        self.assertEqual(self.verify()["variant"], "cn")

    def tf_fixture(self):
        self.expected["variant"] = self.manifest["variant"] = "testflight"
        self.expected["dependencies"] = self.manifest["dependencies"] = "mbedtls@3 fixture"
        self.payloads = {name: b"public TF fixture" for name in
                         ("tf_virtual_client", "libapple_auth.dylib", "libapple_auth_client.dylib")}
        self.manifest["files"] = {name: dict(size=len(data), sha256=hashlib.sha256(data).hexdigest())
                                  for name, data in self.payloads.items()}

    def test_tf_inventory_and_abi(self):
        self.tf_fixture()
        self.assertEqual(self.verify()["variant"], "testflight")

    def test_tf_missing_libraries_refused(self):
        self.tf_fixture()
        del self.payloads["libapple_auth_client.dylib"]
        del self.manifest["files"]["libapple_auth_client.dylib"]
        with self.assertRaisesRegex(ValueError, "inventory_mismatch"):
            self.verify()

    def test_tf_refuses_unrelated_library(self):
        self.tf_fixture()
        self.payloads["libUnexpected.dylib"] = b"refused"
        with self.assertRaisesRegex(ValueError, "invalid_path"):
            self.verify()

    def test_host_gate(self):
        from unittest.mock import patch
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "circleci_required"):
                runtime.provenance(self.root)

    def test_no_existing_destination(self):
        (self.root / "out").mkdir()
        with self.assertRaisesRegex(ValueError, "destination_exists"):
            self.verify()

if __name__ == "__main__":
    unittest.main()
