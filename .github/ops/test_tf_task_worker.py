import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from tf_task_worker import closed,runtime,ensure_membership,native,Stop

def evidence(status="invitation_available",member=False):
    return dict(schema="tf-task-native-v1",status=status,http_status=200,membership_verified=member,
        invitation_open=True,agreement_required=False,downloaded=False,transport_mode="unknown",
        archive_members=0,encrypted_images=0,clear_images=0,downloaded_bytes=0,output_bytes=0)
REQUEST=dict(schema="tf-worker-request-v1",invite="SYNTH123",request_id="tf_"+"a"*32,run_id="123",source_commit="b"*40)
class TFWorkerContracts(unittest.TestCase):
    def env(self):
        return dict(GITHUB_ACTIONS="true",GITHUB_REF="refs/heads/main",GITHUB_RUN_ATTEMPT="1",GITHUB_RUN_ID="123",
            GITHUB_SHA="b"*40,DELIVERY_REQUEST_ID=REQUEST["request_id"],DELIVERY_INVITE="SYNTH123",TF_TASK_MODE="export")
    def state(self,root):
        (root/"invitation.json").write_text(json.dumps({"app":{"bundleId":"example.synthetic","appAdamId":"12345"}}))
    def permit(self):
        return dict({key:REQUEST[key] for key in ("invite","request_id","run_id","source_commit")},
            schema="tf-accept-permit-v1",permitted=True,nonce="c"*32,expires=9999999999)
    def test_profile_rejects_foreign_credentials_or_an_implicit_retry(self):
        self.assertEqual(runtime(self.env()),REQUEST)
        for key,value in (("APPLE_CN_PASSWORD","PRIVATE"),("APPLE_ID","PRIVATE"),("FAIRPLAY_MODEL_B64","PRIVATE"),
                ("GITHUB_RUN_ATTEMPT","2"),("DELIVERY_INVITE","../PRIVATE")):
            env=self.env();env[key]=value
            with self.assertRaises(Stop):runtime(env)
    def test_native_report_is_strict_and_cannot_publish_raw_fields(self):
        closed(evidence())
        for key,value in (("raw","PRIVATE"),("http_status",True),("membership_verified",1),("downloaded",True)):
            item=evidence();item[key]=value
            with self.assertRaises(Stop):closed(item)
    def test_native_receives_binding_but_not_credentials(self):
        env=self.env();env.update(SSHPASS="PRIVATE",DELIVERY_AGE_IDENTITY="PRIVATE",FAIRPLAY_CN_MODEL_B64="PRIVATE")
        completed=Mock(returncode=0,stdout=json.dumps(evidence()).encode())
        with patch("tf_task_worker.subprocess.run",return_value=completed) as run:
            native("inspect",Path("state"),Path("request"),Path("package"),env)
            child=run.call_args.kwargs["env"]
            self.assertEqual(child["GITHUB_RUN_ID"],"123");self.assertEqual(child["GITHUB_SHA"],"b"*40)
            self.assertNotIn("PRIVATE",json.dumps(child))
    def test_existing_membership_never_claims_or_posts(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.state(root)
            runner=Mock(return_value=(0,evidence("membership_verified",True)));remote=Mock()
            ensure_membership(root,root/"request",root,REQUEST,{}, {},runner,remote)
            self.assertEqual(runner.call_args.args[0],"inspect");self.assertEqual(runner.call_count,1);remote.assert_not_called()
    def test_ambiguous_post_is_read_back_and_never_repeated(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.state(root);events=[]
            def remote(op,value,env):
                events.append(op);return self.permit() if op=="claim" else {"recorded":True}
            def runner(mode,*args):
                events.append(mode)
                if mode=="accept":raise TimeoutError("PRIVATE")
                return 0,evidence("membership_verified",True) if events.count("inspect")>1 else evidence()
            receipt={}
            ensure_membership(root,root/"request",root,REQUEST,{},receipt,runner,remote)
            self.assertEqual(events,["inspect","claim","accept","inspect","finish"])
            self.assertTrue(receipt["acceptance_attempted"])
    def test_unverified_outcome_and_prior_intent_cannot_create_another_post(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.state(root);events=[]
            def remote(op,value,env):
                events.append(op)
                if op=="claim":return self.permit()
                self.assertEqual(value["outcome"],"outcome_unknown");return {}
            def runner(mode,*args):
                events.append(mode);return 0,evidence()
            with self.assertRaises(Stop):ensure_membership(root,root/"request",root,REQUEST,{}, {},runner,remote)
            self.assertEqual(events.count("accept"),1)
            runner=Mock(return_value=(0,evidence()));remote=Mock(return_value={"schema":"tf-accept-permit-v1","permitted":False})
            with self.assertRaises(Stop):ensure_membership(root,root/"request",root,REQUEST,{}, {},runner,remote)
            self.assertEqual(runner.call_count,1)
    def test_additional_agreement_stops_before_any_claim(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);self.state(root);result=evidence();result["agreement_required"]=True
            runner=Mock(return_value=(0,result));remote=Mock()
            with self.assertRaises(Stop):ensure_membership(root,root/"request",root,REQUEST,{}, {},runner,remote)
            remote.assert_not_called()
