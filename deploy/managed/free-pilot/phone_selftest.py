"""Phone foreground regression runner for authorized-file tooling.

Downloads only six pinned public software sources from GitHub, checks their
Git blob IDs, then runs the existing synthetic tests with real HTTP blocked.
No real file upload, OAuth, app acquisition, decryption, or background work.
The multi-GiB sparse fixture is deliberately excluded on the phone.
"""
import hashlib
import http.client
import importlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

REF = "f9aa91c54a0d81687bc45dd3d8727034391a4f50"
BASE = "https://raw.githubusercontent.com/zwthys-cyber/ipa-decrypt-lab/" + REF + "/deploy/managed/free-pilot/"
MANIFEST = {
    "private_upload.py": "1654449dc3b26f64627f2e672833c32eaea325c8",
    "archive_verify.py": "a25cb8a0348626c3332a019ee2e89b4e3325c4b7",
    "zip_preflight.py": "7df4bb0e029ccda0d4dcc713c61b580874fed9fb",
    "test_private_upload.py": "d5c198c9b4396a4648d06d291d6bbadef004b70d",
    "test_archive_verify.py": "e875c5ff4ec990625ec9505deb3584c9eccfa741",
    "test_zip_preflight.py": "1992ef3f004471ef33946ad94fa73435c8962402"
}
EXCLUDED = "test_zip_preflight.ArchiveTests.test_sparse_zip64_with_real_offsets_over_4gib"


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def fetch_sources(root):
    for name, expected in MANIFEST.items():
        with urllib.request.urlopen(BASE + name, timeout=30) as response:
            if response.geturl() != BASE + name or response.status != 200:
                raise RuntimeError("source_download_unverified")
            data = response.read(131073)
        if len(data) > 131072:
            raise RuntimeError("source_too_large")
        blob = hashlib.sha1(("blob " + str(len(data)) + "\0").encode("ascii") + data).hexdigest()
        if blob != expected:
            raise RuntimeError("source_digest_mismatch")
        (root / name).write_bytes(data)


def blocked(*args, **kwargs):
    raise AssertionError("live_network_blocked_during_synthetic_tests")


def main():
    os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix="phone-test-", dir=Path.cwd()) as directory:
            root = Path(directory)
            fetch_sources(root)
            print("PINNED_SOURCE_VERIFIED", flush=True)
            original_temp = tempfile.tempdir
            tempfile.tempdir = directory
            sys.path.insert(0, directory)
            try:
                with patch.object(socket.socket, "connect", blocked), \
                     patch.object(socket, "create_connection", blocked), \
                     patch.object(http.client.HTTPConnection, "request", blocked), \
                     patch.object(http.client.HTTPSConnection, "request", blocked):
                    selected = []
                    excluded = []
                    for name in ("test_archive_verify", "test_private_upload", "test_zip_preflight"):
                        module = importlib.import_module(name)
                        for case in cases(unittest.defaultTestLoader.loadTestsFromModule(module)):
                            if case.id() == EXCLUDED:
                                excluded.append(case.id())
                            else:
                                selected.append(case)
                    if len(selected) != 29 or excluded != [EXCLUDED]:
                        raise RuntimeError("test_inventory_mismatch")
                    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(selected))
                    passed = result.wasSuccessful() and result.testsRun == 29 and not result.skipped
                    print(json.dumps({
                        "schema": "phone-synthetic-contract-v1",
                        "platform": sys.platform,
                        "source_ref": REF,
                        "tests_run": result.testsRun,
                        "failures": len(result.failures),
                        "errors": len(result.errors),
                        "skips": len(result.skipped),
                        "large_sparse_fixture_excluded": True,
                        "synthetic_contracts_passed": passed,
                        "live_upload_verified": False,
                        "background_runtime_verified": False,
                        "native_decryption_verified": False
                    }, sort_keys=True))
                    return 0 if passed else 2
            finally:
                sys.path.remove(directory)
                tempfile.tempdir = original_temp
    except Exception as exc:
        print("PHONE_SELFTEST_STOP:", type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
