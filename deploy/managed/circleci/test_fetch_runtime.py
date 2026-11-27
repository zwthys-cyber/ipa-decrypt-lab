import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import fetch_runtime as fetcher

class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workflow = "12345678-1234-1234-1234-123456789abc"
        self.run = "23456789-1234-1234-1234-123456789abc"
        self.expected = dict(commit="a"*40, workflow_id=self.workflow, job_number="40",
            source_fingerprint="b"*64, xcode="fixture", swift="fixture", macos="26.3.1",
            variant="base", dependencies="")
        self.pins = dict(schema="circleci-native-pins-v1", source="a"*40,
                         workflow_id=self.workflow, job_number=40,
                         variants=dict(base=dict(archive_sha256="c"*64, **self.expected)))
        prefix = "/project/" + fetcher.SLUG
        self.rows = {
            prefix + "/job/40":dict(status="success", name="arm64-ios-archive",
                project=dict(id=fetcher.PROJECT, slug=fetcher.SLUG),
                executor=dict(resource_class="m4pro-medium", type="macos"), pipeline=dict(id=self.run)),
            "/runs/" + self.run:dict(data=dict(attributes=dict(phase="ended", current_outcome="succeeded"),
                references=dict(project=dict(id=fetcher.PROJECT), pipeline=dict(id=fetcher.DEFINITION),
                    event=dict(attributes=dict(vcs=dict(
                        origin_repository_url="https://github.com/zwthys-cyber/ipa-decrypt-lab",
                        target_repository_url="https://github.com/zwthys-cyber/ipa-decrypt-lab",
                        branch=fetcher.BRANCH, revision="a"*40)))))),
            "/workflow/" + self.workflow:dict(status="success", pipeline_id=self.run,name="arm64-archive-validation"),
            "/workflow/" + self.workflow + "/job":dict(items=[dict(job_number=40,status="success",name="arm64-ios-archive")])}
        self.artifacts = dict(items=[dict(path="public-arm64-native-runtime/base/native-runtime.tar.gz",
            url="https://output.circle-artifacts.com/output/job/fixture/artifact")])

    def call(self, path):
        return self.rows[path]

    def test_exact_successful_producer(self):
        self.assertTrue(fetcher.trusted_job(self.pins,self.call).endswith("/40/artifacts"))

    def test_wrong_source_or_failed_job_refused(self):
        self.rows["/project/"+fetcher.SLUG+"/job/40"]["status"] = "failed"
        with self.assertRaises(ValueError):
            fetcher.trusted_job(self.pins,self.call)
        self.rows["/project/"+fetcher.SLUG+"/job/40"]["status"] = "success"
        self.rows["/runs/"+self.run]["data"]["references"]["event"]["attributes"]["vcs"]["revision"] = "d"*40
        with self.assertRaises(ValueError):
            fetcher.trusted_job(self.pins,self.call)

    def test_unfinished_or_wrong_workflow_refused(self):
        self.rows["/runs/"+self.run]["data"]["attributes"]["phase"] = "started"
        with self.assertRaisesRegex(ValueError, "not_finished"):
            fetcher.trusted_job(self.pins,self.call)
        self.rows["/runs/"+self.run]["data"]["attributes"]["phase"] = "ended"
        self.rows["/workflow/"+self.workflow]["pipeline_id"] = self.workflow
        with self.assertRaisesRegex(ValueError, "workflow_invalid"):
            fetcher.trusted_job(self.pins,self.call)

    def test_artifact_requires_variant_digest_identity_and_exact_path(self):
        url, digest, expected = fetcher.artifact(self.pins,"base",self.artifacts)
        self.assertEqual(digest,"c"*64)
        self.assertEqual(expected,self.expected)
        with self.assertRaises(ValueError):
            fetcher.artifact(self.pins,"cn",self.artifacts)
        self.pins["variants"]["base"]["commit"] = "d"*40
        with self.assertRaisesRegex(ValueError, "pin_identity"):
            fetcher.artifact(self.pins,"base",self.artifacts)

    def test_untrusted_hosts_and_redirects_refused(self):
        for url in ("http://output.circle-artifacts.com/x","https://evil.invalid/x",
                    "https://output.circle-artifacts.com.evil.invalid/x",
                    "https://user:password@output.circle-artifacts.com/x"):
            self.assertFalse(fetcher.safe_artifact_url(url))
            with self.assertRaises(ValueError):
                fetcher.ArtifactRedirect().redirect_request(None,None,302,"",{},url)
        self.assertTrue(fetcher.safe_artifact_url("https://bucket.s3.amazonaws.com/x"))

    def test_download_digest_and_size_limits_without_network(self):
        payload=b"public fixture"
        class Stream(io.BytesIO):
            status=200
        class Client:
            def open(self,url,timeout):
                return Stream(payload)
        with patch.object(fetcher.urllib.request,"build_opener",return_value=Client()):
            target=self.root/"valid.tar.gz"
            fetcher.download(self.artifacts["items"][0]["url"],target,hashlib.sha256(payload).hexdigest())
            self.assertEqual(target.read_bytes(),payload)
            with self.assertRaisesRegex(ValueError,"digest_mismatch"):
                fetcher.download(self.artifacts["items"][0]["url"],self.root/"bad.tar.gz","f"*64)
            with patch.object(fetcher.runtime,"MAX_ARCHIVE",2):
                with self.assertRaisesRegex(ValueError,"archive_limit"):
                    fetcher.download(self.artifacts["items"][0]["url"],self.root/"large.tar.gz","f"*64)

    def test_native_source_change_rejected_but_docs_do_not_force_rebuild(self):
        root=self.root/"repository"
        root.mkdir()
        def git(*args):
            return subprocess.check_output(["git",*args],cwd=root,text=True).strip()
        git("init","--quiet")
        (root/"tools").mkdir();(root/"tools/native.c").write_text("synthetic native input")
        (root/"README.md").write_text("first")
        def commit():
            git("add",".")
            git("-c","user.name=Fixture","-c","user.email=fixture@example.invalid","commit","--quiet","-m","fixture")
            return git("rev-parse","HEAD")
        original=commit()
        (root/"README.md").write_text("updated documentation")
        commit()
        fetcher.source_gate(root,original)
        (root/"tools/native.c").write_text("changed native input")
        commit()
        with self.assertRaisesRegex(ValueError,"native_source_contract_changed"):
            fetcher.source_gate(root,original)

    def test_host_guard_precedes_execution(self):
        with patch.dict("os.environ",{},clear=True):
            with self.assertRaisesRegex(ValueError,"circleci_required"):
                fetcher.check_host(self.expected)

if __name__ == "__main__":
    unittest.main()
