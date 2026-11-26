// Signed synthetic control path. Production task dispatch/credentials are not enabled here.
import {dispatchSynthetic,finishSynthetic} from "./dispatch.mjs";
import {TRUST,fetchKeys,verifyCircleJWT} from "./oidc.mjs";
import {CONTROL_SCHEMA} from "./control-schema.mjs";
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const JOB=/^pilot_[a-f0-9]{32}$/,HEX=/^[a-f0-9]{32}$/,SHA=/^[a-f0-9]{40}$/;
const OWNER=/^[1-9][0-9]{0,15}$/,SECRET=/^[A-Za-z0-9_-]{43,128}$/;
const ORIGIN=/^https:\/\/ipazake-free-control-pilot\.[a-z0-9][a-z0-9-]{0,62}\.workers\.dev$/;
const BASE="https://circleci.com/api/v2";
export const CONTROL_SQL=Object.freeze({
  admit:`INSERT INTO pilot_jobs(job_id,owner_id,update_id,app_id,region,day,created_at,state)
    SELECT ?,?,?,'123456','default',?,?,'waiting_for_runtime'
    WHERE (SELECT count(*) FROM pilot_jobs WHERE owner_id=? AND day=?)<3
      AND (SELECT count(*) FROM pilot_jobs WHERE owner_id=? AND state='waiting_for_runtime')<30
    ON CONFLICT(owner_id,update_id) DO NOTHING`,
  mark:`INSERT INTO circleci_control_jobs(job_id,source_sha,kind,created_at)
    SELECT job_id,?,'synthetic_noop',? FROM pilot_jobs
    WHERE job_id=? AND owner_id=? AND update_id=? AND state='waiting_for_runtime'
    ON CONFLICT(job_id) DO NOTHING`,
  context:`SELECT p.job_id,p.owner_id,p.state AS pilot_state,c.source_sha,c.kind,
    d.request_id,d.state AS dispatch_state,d.run_id,
    w.worker_job_id,w.finished_at FROM circleci_control_jobs c
    JOIN pilot_jobs p ON p.job_id=c.job_id
    LEFT JOIN circleci_dispatches d ON d.job_id=c.job_id
    LEFT JOIN circleci_claims w ON w.job_id=c.job_id
    WHERE c.job_id=? AND p.owner_id=?`,
  claim:`INSERT INTO circleci_claims(job_id,run_id,worker_job_id,claimed_at)
    SELECT c.job_id,d.run_id,?,? FROM circleci_control_jobs c
    JOIN circleci_dispatches d ON d.job_id=c.job_id JOIN pilot_jobs p ON p.job_id=c.job_id
    WHERE c.job_id=? AND p.owner_id=? AND c.source_sha=?
      AND c.kind='synthetic_noop' AND d.source_sha=c.source_sha AND d.run_id=?
      AND d.state='submitted' AND p.state='waiting_for_runtime'
    ON CONFLICT(job_id) DO NOTHING`,
  finish:`UPDATE circleci_claims SET finished_at=? WHERE job_id=? AND run_id=? AND worker_job_id=?
    AND finished_at IS NULL`
});
function require(ok,reason){if(!ok)throw Error(reason);}
function response(status,value={ok:false}){
  return Response.json(value,{status,headers:{"cache-control":"no-store"}});
}
async function same(left,right){
  const hash=async x=>new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(x)));
  const [a,b]=await Promise.all([hash(left),hash(right)]);
  let n=0;for(let i=0;i<a.length;i++)n|=a[i]^b[i];return n===0;
}
async function body(request,keys){
  require(request.headers.get("content-type")==="application/json"&&request.body,"request_body");
  const reader=request.body.getReader(),chunks=[];let size=0;
  try{
    for(;;){
      const item=await reader.read();if(item.done)break;
      size+=item.value.byteLength;
      require(size<=2048,"request_limit");chunks.push(item.value);
    }
  }finally{try{await reader.cancel();}catch{}reader.releaseLock();}
  const raw=new Uint8Array(size);let at=0;
  for(const part of chunks){raw.set(part,at);at+=part.byteLength;}
  const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(raw));
  require(value&&typeof value==="object"&&!Array.isArray(value)&&
    Object.keys(value).sort().join(",")===[...keys].sort().join(","),"request_fields");
  return value;
}
async function get(send,url){
  const result=await send(url,{method:"GET",redirect:"error",signal:AbortSignal.timeout(10000),
    headers:{accept:"application/json"}});
  require(result.status===200,"provider_pending");
  const raw=await result.text();require(raw.length<=1048576,"provider_limit");return JSON.parse(raw);
}
function config(env,job,now){
  return {enabled:"synthetic-only",owner:env.RUNTIME_OWNER_ID,job,source:env.CIRCLECI_SOURCE_SHA,
    now,token:env.CIRCLECI_API_TOKEN,controlOrigin:env.PILOT_CONTROL_ORIGIN};
}
function configured(env,request){
  return env.PILOT_RUNTIME_MODE==="probe"&&OWNER.test(env.RUNTIME_OWNER_ID||"")&&
    SHA.test(env.CIRCLECI_SOURCE_SHA||"")&&ORIGIN.test(env.PILOT_CONTROL_ORIGIN||"")&&
    new URL(request.url).origin===env.PILOT_CONTROL_ORIGIN&&env.DB?.prepare;
}
async function context(env,job){
  require(JOB.test(job||""),"invalid_job");
  const row=await env.DB.prepare(CONTROL_SQL.context).bind(job,env.RUNTIME_OWNER_ID).first();
  require(row&&row.kind==="synthetic_noop"&&row.source_sha===env.CIRCLECI_SOURCE_SHA,"unbound_job");
  return row;
}
async function authenticated(request,env,value,now,send){
  const token=request.headers.get("authorization")||"";
  require(/^Bearer [A-Za-z0-9_.-]{100,16384}$/.test(token),"invalid_authorization");
  const row=await context(env,value.job_id);
  require(row.pilot_state==="waiting_for_runtime"&&row.dispatch_state==="submitted"&&UUID.test(row.run_id||""),
    "job_not_submitted");
  require(UUID.test(value.worker_job_id||""),"invalid_worker");
  // Preliminary signature check limits unauthenticated provider reads. It is not authorization yet.
  const identity=await verifyCircleJWT(token.slice(7),{run:row.run_id,job:value.worker_job_id},
    await fetchKeys(send),now);
  const run=(await get(send,"https://circleci.com/api/v3/runs/"+row.run_id)).data;
  const refs=run?.references,vcs=refs?.event?.attributes?.vcs;
  require(run?.id===row.run_id&&refs?.project?.id===TRUST.project&&refs?.pipeline?.id===TRUST.definition&&
    vcs?.origin_repository_url==="https://"+TRUST.source&&vcs?.target_repository_url==="https://"+TRUST.source&&
    vcs?.branch===TRUST.ref.slice(11)&&vcs?.revision===row.source_sha,"run_source");
  require(run?.attributes?.phase!=="ended","run_not_active");
  const workflows=(await get(send,BASE+"/pipeline/"+row.run_id+"/workflow")).items;
  require(Array.isArray(workflows)&&workflows.length===1&&workflows[0].name==="synthetic-dispatch-probe"&&
    workflows[0].pipeline_id===row.run_id&&UUID.test(workflows[0].id),"workflow_binding");
  const jobs=(await get(send,BASE+"/workflow/"+workflows[0].id+"/job")).items;
  require(Array.isArray(jobs)&&jobs.length===1&&jobs[0].id===identity.job_id&&
    jobs[0].name==="dispatch-contract-probe"&&jobs[0].status==="running","worker_binding");
  // The identity is authorized only after mapping the signed job to the persisted run and source.
  require(!row.worker_job_id||row.worker_job_id===identity.job_id,"worker_already_bound");
  return {row,identity};
}
async function initialize(env){
  const names=await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('pilot_jobs','pilot_links')").all();
  require(names.success===true&&names.results?.length===2,"pilot_schema_missing");
  const queries=CONTROL_SCHEMA.replace(/^--.*$/gm,"").split(";").map(x=>x.trim()).filter(Boolean);
  const result=await env.DB.batch(queries.map(x=>env.DB.prepare(x)));
  require(result.every(x=>x.success===true),"schema_initialization");
  const required={circleci_dispatches:["job_id","owner_id","request_id","source_sha","state","run_id","created_at","updated_at"],
    circleci_control_jobs:["job_id","source_sha","kind","created_at"],
    circleci_claims:["job_id","run_id","worker_job_id","claimed_at","finished_at"]};
  for(const [table,columns] of Object.entries(required)){
    const result=await env.DB.prepare("PRAGMA table_info("+table+")").all();
    require(result.success===true&&result.results?.map(x=>x.name).join(",")===columns.join(",")&&
      result.results[0].pk===1,"schema_mismatch");
  }
}
export async function handleRuntime(request,env,now=Math.floor(Date.now()/1000),send=fetch){
  const url=new URL(request.url),path=url.pathname;
  const paths=["/v1/runtime/probe-init","/v1/runtime/probe-submit","/v1/runtime/probe-status",
    "/v1/runtime/claim","/v1/runtime/probe-finish"];
  if(request.method!=="POST"||url.search||!paths.includes(path))return response(404);
  if(!configured(env,request))return response(503);
  try{
    if(path.startsWith("/v1/runtime/probe-")&&path!=="/v1/runtime/probe-finish"){
      require(SECRET.test(env.CIRCLECI_CONTROL_TOKEN||"")&&
        ![env.TELEGRAM_WEBHOOK_SECRET,env.PILOT_LINK_ISSUER_TOKEN,env.CIRCLECI_API_TOKEN].includes(env.CIRCLECI_CONTROL_TOKEN),
        "control_configuration");
      if(!await same(request.headers.get("authorization")||"","Bearer "+env.CIRCLECI_CONTROL_TOKEN))return response(401);
      if(path==="/v1/runtime/probe-init"){
        await body(request,[]);await initialize(env);return response(200,{ok:true,schema:"circleci-control-init-v1"});
      }
      if(path==="/v1/runtime/probe-submit"){
        const value=await body(request,["probe_id"]);require(HEX.test(value.probe_id||""),"invalid_probe");
        const job="pilot_"+value.probe_id,update=2**48+parseInt(value.probe_id.slice(0,12),16),day=Math.floor(now/86400);
        const result=await env.DB.batch([
          env.DB.prepare(CONTROL_SQL.admit).bind(job,env.RUNTIME_OWNER_ID,update,day,now,
            env.RUNTIME_OWNER_ID,day,env.RUNTIME_OWNER_ID),
          env.DB.prepare(CONTROL_SQL.mark).bind(env.CIRCLECI_SOURCE_SHA,now,job,env.RUNTIME_OWNER_ID,update)]);
        require(result.every(x=>x.success===true),"admission_storage");
        const row=await context(env,job);
        if(row.dispatch_state)return response(200,{ok:true,job_id:job,state:row.dispatch_state,run_id:row.run_id});
        const dispatched=await dispatchSynthetic(env.DB,config(env,job,now),send);
        return response(dispatched.state==="submitted"?201:409,{ok:dispatched.state==="submitted",job_id:job,...dispatched});
      }
      const value=await body(request,["job_id"]),row=await context(env,value.job_id);
      if(row.dispatch_state==="submitted"&&row.finished_at!==null&&row.worker_job_id)
        await finishSynthetic(env.DB,config(env,value.job_id,now),send);
      const latest=await context(env,value.job_id);
      return response(200,{ok:true,job_id:value.job_id,state:latest.dispatch_state,
        claimed:!!latest.worker_job_id,probe_finished:Number.isSafeInteger(latest.finished_at)});
    }
    const value=await body(request,["job_id","worker_job_id"]);
    const {row,identity}=await authenticated(request,env,value,now,send);
    if(path==="/v1/runtime/claim"){
      const result=await env.DB.prepare(CONTROL_SQL.claim).bind(identity.job_id,now,row.job_id,
        env.RUNTIME_OWNER_ID,row.source_sha,row.run_id).run();
      require(result.success===true,"claim_storage");
      const current=await context(env,row.job_id);
      require(current.worker_job_id===identity.job_id,"claim_lost");
      return response(200,{ok:true,schema:"circleci-control-task-v1",kind:"synthetic_noop",
        job_id:row.job_id,run_id:row.run_id,worker_job_id:identity.job_id,source_sha:row.source_sha});
    }
    require(row.worker_job_id===identity.job_id,"claim_required");
    const result=await env.DB.prepare(CONTROL_SQL.finish).bind(now,row.job_id,row.run_id,identity.job_id).run();
    require(result.success===true,"finish_storage");
    return response(200,{ok:true,schema:"circleci-control-probe-finished-v1"});
  }catch{
    // No provider payload, JWT, token or private task data enters a response or a log.
    return response(409);
  }
}
export default {fetch(request,env){return handleRuntime(request,env);}};
