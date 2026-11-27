"""CI only: saved virtual-session and native TF fixtures; no Apple request or historical resend."""
import base64
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch
import subprocess
import task_context as context
import tf_worker
import test_appstore_worker as fixtures
from test_appstore_worker import archive, model, b64

def session():
    return dict(schema="tf-saved-session-v1",
        profile=dict(schema="testflight-virtual-profile-v1",origin="independent_sdk_virtual_identity",
            run_id="42650873653",source_commit="19244adbe73f71156a91a5c1cb20965925928054",hardware20="a"*40),
        context=dict(accountId="PUBLIC_FIXTURE",sessionId="SYNTHETIC",dsid="123456",udid="a"*40,
            deviceVendorId="SYNTHETIC",deviceName="Mac fixture",deviceModel="Mac14,7",
            headers={"X-Apple-AMD-M":"SYNTHETIC","X-Apple-Store-Front":"143465-1,29"}),
        sdk_state={"identity.json":b64(b"{}")})

class TFTests(unittest.TestCase):
    def setUp(self):
        self.base=fixtures.WorkerTests();self.base.setUp();self.addCleanup(self.base.temp.cleanup)
        self.task=dict(self.base.task,profile="tf",request_id="tf_"+"b"*32,target="SYNTH123")
        self.values=dict(TF_SAVED_SESSION_B64=b64(json.dumps(session()).encode()),FAIRPLAY_CN_MODEL_B64=model())
        self.modes=[];self.member=True;self.ambiguous_accept=False

    def execute(self,binary,args,env,timeout,root,checkpoint):
        if Path(binary).name!="tf_virtual_client":return self.base.execute(binary,args,env,timeout,root,checkpoint)
        checkpoint();args=list(map(str,args));mode=args[1];self.modes.append(mode)
        self.assertEqual(env["CIRCLECI"],"true")
        self.assertEqual(env["RUNTIME_RUN_ID"],self.task["run_id"])
        self.assertFalse(any(k.startswith("GITHUB_") or k.startswith("FAIRPLAY_") or k.startswith("APPLE_") or
            k in ("TF_SAVED_SESSION_B64","DELIVERY_AGE_IDENTITY","CIRCLE_OIDC_TOKEN_V3") for k in env))
        state,request,package=map(Path,args[2:5])
        bound=json.loads(request.read_text())
        self.assertEqual(bound["schema"],"tf-worker-request-circleci-v1")
        self.assertEqual(bound["worker_job_id"],self.task["worker_job_id"])
        (state/"invitation.json").write_text(json.dumps(dict(app=dict(bundleId="example.synthetic",appAdamId="123456"))))
        if mode=="accept":
            if self.ambiguous_accept:raise OSError("synthetic-unknown-post")
            self.member=True
        downloaded=mode=="download"
        if downloaded:archive(package/"beta.ipa")
        value=dict(schema="tf-task-native-v1",status="beta_downloaded" if downloaded else
            "membership_verified" if self.member else "invitation_available",http_status=200,
            membership_verified=self.member,invitation_open=True,agreement_required=False,downloaded=downloaded,
            transport_mode="plain_zip" if downloaded else "unknown",archive_members=4 if downloaded else 0,
            encrypted_images=1 if downloaded else 0,clear_images=0,downloaded_bytes=10000 if downloaded else 0,
            output_bytes=10000 if downloaded else 0)
        return subprocess.CompletedProcess([],0,json.dumps(value),"")

    def export(self,acceptance=None):
        with patch.object(context.platform,"system",return_value="Darwin"),patch.object(context.platform,"machine",return_value="arm64"):
            return tf_worker.export_task(self.task,self.values,self.base.root/"out",self.base.env,
                acceptance=acceptance,load_runtime=self.base.loader,execute=self.execute)

    def test_existing_member_exports_without_claim_or_accept(self):
        calls=[]
        receipt=self.export(lambda *args:calls.append(args))
        self.assertEqual(calls,[]);self.assertEqual(self.modes,["inspect","download"])
        self.assertFalse(receipt["acceptance_attempted"]);self.assertEqual(receipt["app_id"],"123456")
        self.assertEqual(receipt["target_type"],"testflight");self.assertEqual(receipt["testflight_invite"],"SYNTH123")
        self.assertTrue(self.base.seen_clean)

    def test_new_member_stops_without_handoff_broker(self):
        self.member=False
        with self.assertRaisesRegex(ValueError,"acceptance_handoff_required"):self.export()
        self.assertEqual(self.modes,["inspect"]);self.assertFalse((self.base.root/"out").exists())

    def test_one_permit_one_post_then_readback(self):
        self.member=False;calls=[]
        def broker(action,args,task):
            calls.append((action,args))
            if action=="claim":return dict(args,schema="tf-accept-permit-v1",permitted=True,nonce="d"*32,expires=int(time.time())+300)
            return dict(ok=True)
        receipt=self.export(broker)
        self.assertEqual(self.modes,["inspect","accept","inspect","download"])
        self.assertTrue(receipt["acceptance_attempted"]);self.assertEqual([a for a,_ in calls],["claim","finish"])
        self.assertEqual(calls[-1][1]["outcome"],"membership_verified")

    def test_ambiguous_accept_stays_unknown_and_never_posts_twice(self):
        self.member=False;self.ambiguous_accept=True;calls=[]
        def broker(action,args,task):
            calls.append((action,args))
            return dict(args,schema="tf-accept-permit-v1",permitted=True,nonce="d"*32,expires=int(time.time())+300)
        with self.assertRaises(tf_worker.Stop):self.export(broker)
        self.assertEqual(self.modes,["inspect","accept","inspect"])
        self.assertEqual(calls[-1][1]["outcome"],"outcome_unknown")
        self.assertFalse((self.base.root/"out").exists())

    def test_wrong_virtual_identity_is_rejected_without_native_call(self):
        value=session();value["context"]["udid"]="f"*40
        self.values["TF_SAVED_SESSION_B64"]=b64(json.dumps(value).encode())
        with self.assertRaises(ValueError):self.export()
        self.assertEqual(self.modes,[])

    def test_unsafe_sdk_path_and_delivery_private_key_are_rejected(self):
        value=session();value["sdk_state"]["../escaped.txt"]=b64(b"bad")
        self.values["TF_SAVED_SESSION_B64"]=b64(json.dumps(value).encode())
        with self.assertRaises(ValueError):self.export()
        self.values["TF_SAVED_SESSION_B64"]=b64(json.dumps(session()).encode())
        self.values["DELIVERY_AGE_IDENTITY"]="must-never-reach-circleci"
        with self.assertRaisesRegex(ValueError,"profile_fields"):self.export()
        self.assertEqual(self.modes,[])

if __name__=="__main__":unittest.main()
