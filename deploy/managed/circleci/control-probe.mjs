// Invoked inside the credential-free Linux job. Never log the authorization header.
import {writeFileSync} from "node:fs";
const origin=process.env.PROBE_CONTROL_URL||"",job=process.env.PROBE_CONTROL_JOB||"";
if(!origin&&!job){
  console.log(JSON.stringify({schema:"circleci-control-probe-v1",skipped:true}));
}else{
  try{
    if(!/^https:\/\/ipazake-free-control-pilot\.[a-z0-9][a-z0-9-]{0,62}\.workers\.dev$/.test(origin)||
       !/^pilot_[a-f0-9]{32}$/.test(job)||!process.env.CIRCLE_OIDC_TOKEN_V3)
      throw Error("control_probe_configuration");
    const body=JSON.stringify({job_id:job,worker_job_id:process.env.CIRCLE_WORKFLOW_JOB_ID});
    async function call(path){
      const result=await fetch(origin+path,{method:"POST",redirect:"error",signal:AbortSignal.timeout(15000),
        headers:{"user-agent":"ipa-decrypt-circleci-runtime/0.2","content-type":"application/json",authorization:"Bearer "+process.env.CIRCLE_OIDC_TOKEN_V3},body});
      if(![200,409,503].includes(result.status))throw Error("control_probe_response");
      if(result.status!==200){
        let detail;try{detail=await result.json();}catch{}
        const code=/^[a-z_]{1,40}$/.test(detail?.code||"")?detail.code:"control_pending";
        console.log(JSON.stringify({schema:"circleci-control-retry-v1",stage:path,code}));
        return null;
      }
      return result.json();
    }
    let task;
    for(let attempt=0;attempt<8&&!task;attempt++){
      if(attempt)await new Promise(resolve=>setTimeout(resolve,2000));
      task=await call("/v1/runtime/claim");
    }
    if(!task||task.kind!=="synthetic_noop"||task.job_id!==job||task.source_sha!==process.env.CIRCLE_SHA1||
       task.run_id!==process.env.PROBE_PIPELINE||task.worker_job_id!==process.env.CIRCLE_WORKFLOW_JOB_ID)
      throw Error("control_probe_claim");
    // A synthetic task intentionally has no Apple operation, file upload or Telegram send.
    let done;
    for(let attempt=0;attempt<3&&!done;attempt++){
      if(attempt)await new Promise(resolve=>setTimeout(resolve,1000));
      done=await call("/v1/runtime/probe-finish");
    }
    if(done?.ok!==true||done.schema!=="circleci-control-probe-finished-v1")throw Error("control_probe_finish");
    const receipt={schema:"circleci-control-probe-v1",skipped:false,claimed:true,finished:true,
      production:false,apple_operation:false,file_upload:false,telegram_send:false,
      job_id:job,run_id:process.env.PROBE_PIPELINE,source_commit:process.env.CIRCLE_SHA1};
    writeFileSync("dispatch-probe-out/control-receipt.json",JSON.stringify(receipt)+"\n",{mode:0o600});
    console.log(JSON.stringify(receipt));
  }catch{
    console.error("circleci_control_probe_failed");process.exitCode=1;
  }
}
