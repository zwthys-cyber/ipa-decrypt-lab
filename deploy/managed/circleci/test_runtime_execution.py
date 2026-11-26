"""GitHub-only dispatcher tests; native/account/Drive transports are synthetic."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from credential_envelope import PROFILES
import runtime_execution as worker

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.calls=[];self.cancel=False
  self.task=dict(profile="default",job_id="pilot_"+"a"*32,worker_job_id="12345678-1234-1234-1234-123456789abc",deadline=int(time.time())+300)
  self.env=dict(PATH="/synthetic-only",CIRCLECI="true")
 def rpc(self,path,value):
  self.calls.append((path,value))
  if path=="checkpoint":return dict(proceed=not self.cancel,deadline=self.task["deadline"])
  return dict(ok=True)
 def values(self):return {key:"synthetic-only" for key in PROFILES[self.task["profile"]]}
 def test_default_and_cn_call_matching_adapter_and_durable_delivery(self):
  for profile in ("default","cn"):
   self.task["profile"]=profile;self.calls=[]
   def adapter(task,values,output,env,checkpoint,**kwargs):
    self.assertEqual(task["profile"],profile);self.assertEqual(set(values),PROFILES[profile])
    self.assertIs(env,self.env);self.assertEqual(output,self.root/"private-output")
    record=kwargs["delivery"](self.root/"unused-fixture.ipa",{"fixture":True})
    return dict(private_delivery=record)
   with patch("appstore_worker.export_task",side_effect=adapter) as actual,patch.object(worker,"deliver",return_value=dict(file_id="SYNTHETIC_12345")) as upload:
    worker.execute_export(self.task,self.values(),self.root,self.env,self.rpc,"https://fixture.invalid",None)
    self.assertEqual(actual.call_count,1);self.assertEqual(upload.call_count,1)
    self.assertEqual(self.calls[-1][0],"export-finish")
    self.assertEqual(upload.call_args.args[3]["worker_job_id"],self.task["worker_job_id"])
 def test_tf_uses_saved_session_adapter_and_bound_acceptance_callback(self):
  self.task["profile"]="tf"
  def adapter(task,values,output,env,checkpoint,**kwargs):
   self.assertEqual(set(values),PROFILES["tf"])
   args=dict(invite="SyntheticInvite",request_id="tf_"+"b"*32)
   kwargs["acceptance"]("claim",args,task)
   return dict(private_delivery=dict(file_id="SYNTHETIC_12345"))
  with patch("tf_worker.export_task",side_effect=adapter) as actual:
   worker.execute_export(self.task,self.values(),self.root,self.env,self.rpc,"https://fixture.invalid",None)
   self.assertEqual(actual.call_count,1)
  permit=next(value for path,value in self.calls if path=="tf-permit")
  self.assertEqual(permit["job_id"],self.task["job_id"]);self.assertEqual(permit["action"],"claim")
 def test_cancel_stops_before_native_adapter(self):
  self.cancel=True
  with patch("appstore_worker.export_task") as actual:
   with self.assertRaises(InterruptedError):worker.execute_export(self.task,self.values(),self.root,self.env,self.rpc,"https://fixture.invalid",None)
   actual.assert_not_called()
  self.assertFalse(any(path=="export-finish" for path,value in self.calls))
 def test_wrong_profile_credentials_fail_before_issuing_requests(self):
  with self.assertRaises(ValueError):worker.execute_export(self.task,{"APPLE_CN_SESSION_B64":"synthetic"},self.root,self.env,self.rpc,"https://fixture.invalid",None)
  self.assertEqual(self.calls,[])
 def test_adapter_failure_or_missing_private_registration_never_finishes(self):
  for outcome in (RuntimeError("synthetic"),{}):
   self.calls=[]
   with patch("appstore_worker.export_task",side_effect=outcome if isinstance(outcome,Exception) else None,return_value=outcome):
    with self.assertRaises((RuntimeError,ValueError)):
     worker.execute_export(self.task,self.values(),self.root,self.env,self.rpc,"https://fixture.invalid",None)
   self.assertFalse(any(path=="export-finish" for path,value in self.calls))
 def test_checkpoint_throttles_polls_without_ignoring_forced_cancel(self):
  clock=[100]
  checkpoint=worker.Checkpoint(self.task,self.rpc,dict(job_id=self.task["job_id"]),lambda:clock[0])
  checkpoint("downloading")
  for _ in range(20):checkpoint()
  self.assertEqual(len(self.calls),1)
  self.cancel=True
  with self.assertRaises(InterruptedError):checkpoint(force=True)
 def test_expired_task_never_enters_another_network_request(self):
  import managed_worker as manager
  with patch.object(manager,"TASK_DEADLINE",time.time()-1),patch.object(manager,"rpc_once") as transport:
   with self.assertRaises(InterruptedError):manager.rpc("checkpoint",{})
   transport.assert_not_called()
if __name__=="__main__":unittest.main()
