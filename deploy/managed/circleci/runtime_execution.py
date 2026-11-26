"""Connect claimed real tasks to the existing fully verifying adapters and durable uploader."""
import time
from task_context import require,credentials
from runtime_uploader import deliver

class Checkpoint:
 def __init__(self,task,rpc,identity,clock=time.monotonic):
  self.task=task;self.rpc=rpc;self.identity=identity;self.clock=clock;self.last=-100;self.stage="working"
 def __call__(self,stage="working",force=False):
  require(int(time.time())<self.task["deadline"],"managed_task_expired")
  if stage!="working":self.stage=stage
  stamp=self.clock()
  if force or stamp-self.last>=5:
   result=self.rpc("checkpoint",dict(self.identity,stage=self.stage))
   require(result.get("deadline")==self.task["deadline"],"managed_checkpoint_binding")
   if result.get("proceed") is not True:raise InterruptedError("cancelled")
   self.last=stamp

def execute_export(task,values,root,env,rpc,origin,load_runtime):
 profile=task["profile"]
 require(profile in ("default","cn","tf"),"managed_export_profile")
 values=credentials(profile,values)
 identity=dict(job_id=task["job_id"],worker_job_id=task["worker_job_id"])
 checkpoint=Checkpoint(task,rpc,identity)
 checkpoint("loading_runtime",force=True)
 def upload(path,receipt):
  checkpoint("uploading_private",force=True)
  return deliver(path,receipt,rpc,identity,origin,lambda:checkpoint(force=True))
 def permit(action,args,unused_task):
  checkpoint("checking_acceptance_permit",force=True)
  return rpc("tf-permit",dict(identity,action=action,args=args))
 if profile=="tf":
  from tf_worker import export_task
  receipt=export_task(task,values,root/"private-output",env,checkpoint,acceptance=permit,
   load_runtime=load_runtime,delivery=upload)
 else:
  from appstore_worker import export_task
  receipt=export_task(task,values,root/"private-output",env,checkpoint,
   load_runtime=load_runtime,delivery=upload)
 checkpoint("artifact_ready",force=True)
 require(receipt.get("private_delivery") and receipt["private_delivery"].get("file_id"),"managed_delivery_unconfirmed")
 finished=rpc("export-finish",dict(identity,receipt=receipt))
 return dict(receipt,_notification_confirmed=finished.get("notification_confirmed") is True)
