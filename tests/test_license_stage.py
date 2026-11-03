import plistlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from license_stage import prepare
from private_trial import engine_diagnostics

class LicenseStageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root/"Payload/Demo.app"
        (self.bundle/"SC_Info").mkdir(parents=True)
        (self.bundle/"SC_Info/Demo.sinf").write_bytes(b"synthetic")
        self.audit = {"main_executable": "Payload/Demo.app/Demo",
                      "binaries": [{"path": "Payload/Demo.app/Demo"},
                                   {"path": "Payload/Demo.app/Frameworks/F.framework/F"}]}
        self.target = "Frameworks/F.framework/SC_Info/F.sinf"
    def manifest(self, targets, sources=None):
        (self.bundle/"SC_Info/Manifest.plist").write_bytes(plistlib.dumps({
            "SinfPaths": sources if sources is not None else ["SC_Info/Demo.sinf"],
            "SinfReplicationPaths": targets,
        }))
    def test_replication_preserves_source_and_never_claims_authorization(self):
        self.manifest([self.target])
        result = prepare(self.root, self.audit)
        self.assertEqual((self.bundle/self.target).read_bytes(), b"synthetic")
        self.assertEqual((self.bundle/"SC_Info/Demo.sinf").read_bytes(), b"synthetic")
        self.assertEqual(result["replicated"], 1)
        self.assertEqual(result["binary_sinf_present"], 2)
        self.assertFalse(result["authorization_verified"])
        self.assertEqual(prepare(self.root, self.audit)["replicated"], 0)
    def test_traversal_rejected_before_any_write(self):
        self.manifest([self.target, "../SC_Info/escape.sinf"])
        with self.assertRaises(ValueError):
            prepare(self.root, self.audit)
        self.assertFalse((self.bundle/self.target).exists())
    def test_conflicting_target_is_preserved(self):
        self.manifest([self.target])
        target = self.bundle/self.target
        target.parent.mkdir(parents=True)
        target.write_bytes(b"preserve")
        with self.assertRaises(ValueError):
            prepare(self.root, self.audit)
        self.assertEqual(target.read_bytes(), b"preserve")
    def test_distinct_source_licenses_are_not_guessed(self):
        (self.bundle/"SC_Info/Second.sinf").write_bytes(b"different")
        self.manifest([self.target], ["SC_Info/Demo.sinf", "SC_Info/Second.sinf"])
        self.assertTrue(prepare(self.root, self.audit)["ambiguous_sources"])
        self.assertFalse((self.bundle/self.target).exists())
    def test_license_symlink_rejected(self):
        outside = self.root/"outside"
        outside.mkdir()
        (self.bundle/"Frameworks").symlink_to(outside, target_is_directory=True)
        self.manifest([self.target])
        with self.assertRaises(ValueError):
            prepare(self.root, self.audit)
    def test_preflight_does_not_count_as_native_call(self):
        result = SimpleNamespace(stdout="", stderr="encrypted start is not host-page aligned", returncode=4)
        self.assertEqual(engine_diagnostics(result), ("unsupported_start_alignment", False, None))
    def test_actual_errno_is_counted_without_raw_data(self):
        result = SimpleNamespace(stdout='{"event":"native_call","requested_cryptid":2}\n{"event":"native_return","return_code":-1,"errno":1}\n',
                                 stderr="secret-path", returncode=4)
        self.assertEqual(engine_diagnostics(result), ("native_rejected_or_invalid_result", True, 1))
    def test_fault_after_call_is_distinct(self):
        result = SimpleNamespace(stdout='{"event":"native_call","requested_cryptid":2}\n',
                                 stderr="", returncode=4)
        self.assertEqual(engine_diagnostics(result), ("native_fault_or_incomplete", True, None))
