import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("circle_probe", Path(__file__).with_name("probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.ident = "12345678-1234-1234-1234-123456789abc"
        self.definition = dict(id=self.ident,
            config_source=dict(provider="github_app", file_path=".circleci/config.yml",
                               repo=dict(full_name=probe.REPO)),
            checkout_source=dict(provider="github_app", repo=dict(full_name=probe.REPO)))
        self.env = dict(CIRCLECI="true", CIRCLE_SHA1="a"*40, CIRCLE_BRANCH=probe.BRANCH,
                        CIRCLE_WORKFLOW_ID=self.ident, CIRCLE_BUILD_NUM="18")

    def test_select_exact_definition(self):
        self.assertEqual(probe.select_definition(dict(items=[self.definition])), self.ident)

    def test_ambiguous_definition(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            probe.select_definition(dict(items=[self.definition, self.definition]))

    def test_foreign_repository_and_config_refused(self):
        for section, field, value in (("config_source", "provider", "github_oauth"),
                                      ("checkout_source", "provider", "gitlab"),
                                      ("config_source", "file_path", "other.yml")):
            item = copy.deepcopy(self.definition)
            item[section][field] = value
            with self.assertRaises(ValueError):
                probe.select_definition(dict(items=[item]))
        item = copy.deepcopy(self.definition)
        item["checkout_source"]["repo"]["full_name"] = "foreign/repo"
        with self.assertRaises(ValueError):
            probe.select_definition(dict(items=[item]))

    def test_nonsecret_fixed_probe_payload(self):
        body = probe.payload(self.ident, "a"*40, "b"*32)
        self.assertEqual(body["config"], dict(branch=probe.BRANCH))
        self.assertEqual(body["checkout"], dict(branch=probe.BRANCH))
        self.assertEqual(body["parameters"], dict(dispatch_probe=True, probe_source="a"*40,
                                                 probe_id="b"*32, build_native_runtime=False))

    def test_payload_identity_rejected(self):
        for values in (("bad", "a"*40, "b"*32), (self.ident, "main", "b"*32),
                       (self.ident, "a"*40, "secret\n")):
            with self.assertRaises(ValueError):
                probe.payload(*values)

    def test_worker_bound_receipt(self):
        value = probe.worker_receipt("a"*40, "b"*32, self.ident, self.env)
        self.assertFalse(value["production"])
        self.assertEqual(value["commit"], "a"*40)

    def test_worker_source_branch_and_provider_guards(self):
        for key, value in (("CIRCLE_SHA1", "c"*40), ("CIRCLE_BRANCH", "main"),
                           ("CIRCLECI", "false"), ("GITHUB_ACTIONS", "true"),
                           ("CIRCLE_BUILD_NUM", "0"), ("CIRCLE_WORKFLOW_ID", "bad")):
            env = dict(self.env, **{key:value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.worker_receipt("a"*40, "b"*32, self.ident, env)

    def test_api_path_rejected_before_transport(self):
        for path in ("https://evil.invalid", "/context", "/project/../context", "/project/x?token=x"):
            with self.assertRaisesRegex(ValueError, "invalid_api_path"):
                probe.api("private-fixture", path)

    def test_redirect_does_not_forward_credentials(self):
        self.assertIsNone(probe.NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.invalid"))

if __name__ == "__main__":
    unittest.main()
