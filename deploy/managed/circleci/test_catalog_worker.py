"""CI-only synthetic catalog transport and credential isolation; no Apple requests."""
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import test_appstore_worker as fixtures
import task_context
import catalog_worker as worker
import cn_profile
import credential_envelope as envelope
from publish_credentials import values as publish_values

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.WorkerTests(methodName="runTest")
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.task=self.fixture.task
        self.values={k:self.fixture.values[k] for k in ("APPLE_ID","APPLE_PASSWORD")}
        self.calls=[];self.bad_output=False;self.create_ipa=False;self.change_account=False;self.reject_resume=False
        self.output="IPA_LAB_CATALOG_TOTAL:12\nIPA_LAB_CATALOG_ITEM:123456789:1.2.3:2026-10-01\nIPA_LAB_CATALOG_NEXT:123456789\n"

    def execute(self,binary,args,env,timeout,root,checkpoint):
        checkpoint();args=list(map(str,args));self.calls.append((Path(binary).name,args,dict(env),root))
        self.assertGreater(timeout,0)
        if args==["--prewarm"]:
            return subprocess.CompletedProcess([],0 if env.get("LAB_KBSYNC_CHILD")=="1" else 2,"","")
        if args[0]=="resume-cn" and self.reject_resume:
            return subprocess.CompletedProcess([],1,"private-native-account-output","")
        if args[0]=="download":
            self.assertEqual(env["LAB_VERSION_CATALOG"],"1")
            self.assertEqual(env["LAB_CATALOG_PAGED"],"1")
            if self.create_ipa:Path(args[args.index("--output")+1]).write_bytes(b"unexpected-package")
            if self.change_account:
                path=next(Path(env["HOME"]).glob(".ipatool/*/account.json"))
                value=json.loads(path.read_text());value["store"]="143441";path.write_text(json.dumps(value))
            return subprocess.CompletedProcess([],0,"private-native-account-output" if self.bad_output else self.output,"")
        return subprocess.CompletedProcess([],0,"","")

    def query(self,before="",checkpoint=lambda stage:None):
        with patch.object(task_context.platform,"system",return_value="Darwin"),patch.object(task_context.platform,"machine",return_value="arm64"),patch.object(worker,"check_app",return_value=dict(bundleId="example.synthetic")):
            return worker.query_catalog(self.task,self.values,before,self.fixture.env,checkpoint,
                self.fixture.loader,self.execute)

    def make_cn(self):
        self.task.update(profile="cn",request_id="cn_"+"b"*32)
        full=fixtures.cn_values()
        self.values={k:full[k] for k in envelope.PROFILES["cn_catalog"]}

    def test_default_page_binding_private_environment_and_cleanup(self):
        result=self.query()
        self.assertEqual(result["source_sha"],self.task["source_sha"])
        self.assertEqual(result["worker_job_id"],self.task["worker_job_id"])
        self.assertEqual(result["rows"],[dict(id="123456789",version="1.2.3",date="2026-10-01")])
        self.assertEqual(result["next_before"],"123456789")
        self.assertNotIn("private-native-account-output",json.dumps(result))
        for name,args,env,root in self.calls:
            self.assertEqual("APPLEPACKAGE_PASSWORD" in env,args[0]=="login")
            self.assertEqual(env.get("LAB_KBSYNC_CHILD")=="1",name=="lab-kbsync")
            self.assertFalse(any(k.startswith(("FAIRPLAY_","GITHUB_","CIRCLE")) or k.endswith("_TOKEN") for k in env))
            self.assertFalse(root.exists())

    def test_cn_uses_only_saved_session_no_model_password_login_or_logout(self):
        self.make_cn();self.query()
        commands=[args[0] for _,args,_,_ in self.calls]
        self.assertIn("resume-cn",commands);self.assertNotIn("login",commands);self.assertNotIn("logout",commands)
        self.assertFalse(any("APPLEPACKAGE_PASSWORD" in env for _,_,env,_ in self.calls))

    def test_cn_expiry_requires_maintenance_without_password_fallback(self):
        self.make_cn();self.reject_resume=True
        with self.assertRaisesRegex(ValueError,"cn_session_requires_maintenance"):self.query()
        self.assertFalse(any(args[0] in ("login","download") for _,args,_,_ in self.calls))

    def test_cn_account_change_after_query_is_rejected(self):
        self.make_cn();self.change_account=True
        with self.assertRaisesRegex(ValueError,"cn_account_binding"):self.query()

    def test_catalog_rejects_export_credentials_before_native_calls(self):
        for profile,full in (("default",self.fixture.values),("cn",fixtures.cn_values())):
            self.task.update(profile=profile,request_id=("cn_" if profile=="cn" else "")+"b"*32)
            self.values=full
            with self.assertRaisesRegex(ValueError,"lease_profile_fields"):self.query()
        self.assertEqual(self.calls,[])

    def test_unexpected_ipa_or_unparseable_output_is_rejected_and_removed(self):
        for flag in ("create_ipa","bad_output"):
            setattr(self,flag,True)
            with self.assertRaises(ValueError):self.query()
            setattr(self,flag,False)
        self.assertTrue(all(not root.exists() for _,_,_,root in self.calls))

    def test_page_must_advance_and_cursor_is_passed_to_native(self):
        with self.assertRaisesRegex(ValueError,"catalog_invalid"):self.query("123456789")
        self.query("223456789")
        self.assertEqual(next(env["LAB_CATALOG_BEFORE"] for _,args,env,_ in reversed(self.calls) if args[0]=="download"),"223456789")
        for before in ("0","12345","123456;bad",None):
            with self.assertRaisesRegex(ValueError,"catalog_cursor"):self.query(before)

    def test_cancel_before_query_leaves_no_native_query_or_private_directory(self):
        def stop(stage):
            if stage=="catalog_query":raise InterruptedError("cancelled")
        with self.assertRaises(InterruptedError):self.query(checkpoint=stop)
        self.assertFalse(any(args[0]=="download" for _,args,_,_ in self.calls))
        self.assertTrue(all(not root.exists() for _,_,_,root in self.calls))

    def test_runtime_digest_failure_precedes_account_access(self):
        self.fixture.runtime_bad=True
        with self.assertRaisesRegex(ValueError,"runtime_fetch_proof"):self.query()
        self.assertEqual(self.calls,[])

    def test_catalog_roles_publisher_cannot_include_model_or_cross_profile_secrets(self):
        env=dict(self.fixture.values,**fixtures.cn_values(),DELIVERY_AGE_IDENTITY="forbidden",TELEGRAM_BOT_TOKEN="forbidden")
        for role in ("default_catalog","cn_catalog"):
            value=publish_values(role,env)
            self.assertEqual(set(value),envelope.PROFILES[role])
            for forbidden in ("FAIRPLAY_MODEL_B64","FAIRPLAY_CN_STATE_B64","APPLE_PASSWORD" if role=="cn_catalog" else "APPLE_CN_SESSION_B64"):
                with self.assertRaisesRegex(ValueError,"lease_profile_fields"):
                    envelope.credentials(role,dict(value,**{forbidden:"forbidden"}))
        with self.assertRaisesRegex(ValueError,"lease_profile_fields"):cn_profile.decode(self.values)

if __name__=="__main__":unittest.main()
