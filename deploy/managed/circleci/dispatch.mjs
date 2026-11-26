// Durable, synthetic-only CircleCI dispatch candidate. Not wired to the live bot.
import {TRUST} from "./oidc.mjs";
const JOB=/^pilot_[a-f0-9]{32}$/, OWNER=/^[1-9][0-9]{0,15}$/, SHA=/^[a-f0-9]{40}$/;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
export const DISPATCH_SQL=Object.freeze({
  claim:`INSERT INTO circleci_dispatches(job_id,owner_id,request_id,source_sha,state,created_at,updated_at)
    SELECT job_id,owner_id,?,?,'intent',?,? FROM pilot_jobs
    WHERE job_id=? AND owner_id=? AND state='waiting_for_runtime'
      AND NOT EXISTS (SELECT 1 FROM pilot_links WHERE job_id=pilot_jobs.job_id)
      AND NOT EXISTS (SELECT 1 FROM circleci_dispatches d WHERE d.state IN ('intent','submitted','unknown')
        AND NOT EXISTS (SELECT 1 FROM circleci_probe_resolutions r WHERE r.job_id=d.job_id AND r.source_sha=d.source_sha))
    ON CONFLICT(job_id) DO NOTHING`,
  submitted:`UPDATE circleci_dispatches SET state='submitted',run_id=?,updated_at=?
    WHERE job_id=? AND owner_id=? AND request_id=? AND source_sha=? AND state='intent'`,
  unknown:`UPDATE circleci_dispatches SET state='unknown',updated_at=?
    WHERE job_id=? AND owner_id=? AND request_id=? AND source_sha=? AND state='intent'`,
  get:"SELECT * FROM circleci_dispatches WHERE job_id=? AND owner_id=?",
  finish:`UPDATE circleci_dispatches SET state='finished',updated_at=?
    WHERE job_id=? AND owner_id=? AND request_id=? AND source_sha=? AND run_id=? AND state='submitted'`
});
function valid(config){
  return config?.enabled==="synthetic-only"&&JOB.test(config.job||"")&&OWNER.test(config.owner||"")&&
    SHA.test(config.source||"")&&typeof config.token==="string"&&config.token.length>=16&&
    !/[\r\n]/.test(config.token)&&Number.isSafeInteger(config.now)&&config.now>=0;
}
function changed(result){
  if(result?.success!==true||![0,1].includes(result.meta?.changes))throw Error("dispatch_storage");
  return result.meta.changes===1;
}
function identity(c,id){return [c.job,c.owner,id,c.source];}
async function read(response){
  const text=await response.text();
  if(text.length>65536)throw Error("dispatch_response_limit");
  return JSON.parse(text);
}
export async function dispatchSynthetic(db,config,send=fetch){
  if(!valid(config))return {state:"disabled"};
  const request=crypto.randomUUID().replaceAll("-","");
  // A committed intent precedes the only external POST. An uncertain commit sends nothing.
  let claimed;
  try{
    claimed=changed(await db.prepare(DISPATCH_SQL.claim).bind(request,config.source,config.now,
      config.now,config.job,config.owner).run());
  }catch{return {state:"storage_unavailable"};}
  if(!claimed)return {state:"blocked"};
  let failure="dispatch_transport_unknown";
  try{
    const parameters={dispatch_probe:true,probe_source:config.source,probe_id:request,build_native_runtime:false};
    if(config.controlOrigin!==undefined){
      if(!/^https:\/\/ipazake-free-control-pilot\.[a-z0-9][a-z0-9-]{0,62}\.workers\.dev$/.test(config.controlOrigin))
        throw Error("dispatch_control_origin");
      parameters.control_probe_url=config.controlOrigin;
      parameters.control_probe_job=config.job;
    }
    const response=await send("https://circleci.com/api/v3/runs",{
      method:"POST",redirect:"error",signal:AbortSignal.timeout(15000),
      headers:{"user-agent":"ipa-decrypt-control-plane/0.2",authorization:"Bearer "+config.token,"content-type":"application/json",accept:"application/json"},
      body:JSON.stringify({data:{attributes:{config:{branch:TRUST.ref.slice(11)},
        checkout:{branch:TRUST.ref.slice(11)},parameters},references:{pipeline:{id:TRUST.definition}}}})
    });
    failure="dispatch_http_"+String(response.status);
    if(response.status!==201)throw Error("dispatch_unconfirmed");
    failure="dispatch_response_invalid";
    const value=await read(response),run=value?.data?.id;
    if(!UUID.test(run||""))throw Error("dispatch_unconfirmed");
    failure="dispatch_storage_unconfirmed";
    const stored=changed(await db.prepare(DISPATCH_SQL.submitted).bind(run,config.now,...identity(config,request)).run());
    if(!stored)throw Error("dispatch_storage");
    return {state:"submitted",run_id:run};
  }catch(error){
    if(failure==="dispatch_transport_unknown"&&["TypeError","TimeoutError","AbortError"].includes(error?.name))
      failure="dispatch_transport_"+error.name.toLowerCase();
    try{
      await db.prepare("INSERT INTO circleci_dispatch_diagnostics(job_id,code,recorded_at) VALUES(?,?,?) ON CONFLICT(job_id) DO NOTHING")
        .bind(config.job,failure,config.now).run();
    }catch{}
    try{await db.prepare(DISPATCH_SQL.unknown).bind(config.now,...identity(config,request)).run();}catch{}
    return {state:"unknown"};
  }
}
export async function finishSynthetic(db,config,send=fetch){
  if(!valid(config))return {state:"disabled"};
  const row=await db.prepare(DISPATCH_SQL.get).bind(config.job,config.owner).first();
  if(!row||row.state!=="submitted"||row.source_sha!==config.source||!UUID.test(row.run_id||""))
    return {state:"blocked"};
  // Readback may be repeated for the same known ID; it never dispatches another run.
  const response=await send("https://circleci.com/api/v3/runs/"+row.run_id,{
    method:"GET",redirect:"error",signal:AbortSignal.timeout(15000),headers:{"user-agent":"ipa-decrypt-control-plane/0.2",authorization:"Bearer "+config.token,accept:"application/json"}});
  if(response.status!==200)return {state:"pending"};
  const value=await read(response),run=value?.data,refs=run?.references;
  const vcs=refs?.event?.attributes?.vcs;
  if(run?.id!==row.run_id||refs?.project?.id!==TRUST.project||refs?.pipeline?.id!==TRUST.definition||
     vcs?.origin_repository_url!=="https://"+TRUST.source||vcs?.target_repository_url!=="https://"+TRUST.source||
     vcs?.branch!==TRUST.ref.slice(11)||vcs?.revision!==row.source_sha)
    throw Error("dispatch_readback_identity");
  if(run?.attributes?.phase!=="ended"||run?.attributes?.current_outcome!=="succeeded")
    return {state:"pending"};
  const done=changed(await db.prepare(DISPATCH_SQL.finish).bind(config.now,...identity(config,row.request_id),row.run_id).run());
  return {state:done?"finished":"blocked"};
}
