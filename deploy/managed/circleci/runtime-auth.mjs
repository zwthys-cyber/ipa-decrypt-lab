import {TRUST,verifyCircleJWT,fetchKeys} from "./oidc.mjs";
import {GITHUB_TRUST,verifyGithubJWT,fetchGithubKeys} from "./github-oidc.mjs";
export const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
export function need(ok,code){if(!ok)throw Error(code);}
export async function publicJSON(send,url){
 const reply=await send(url,{method:"GET",redirect:"manual",signal:AbortSignal.timeout(10000),
  headers:{"user-agent":"ipa-decrypt-managed-runtime/0.2",accept:"application/json"}});
 need(reply.status===200,"runtime_provider_pending");
 const text=await reply.text();need(text.length<=262144,"runtime_provider_limit");return JSON.parse(text);
}
export async function circleIdentity(request,env,task,worker,now,send){
 const token=request.headers.get("x-ipazake-job-token")||"";
 need(/^[A-Za-z0-9_.-]{100,16384}$/.test(token)&&UUID.test(worker||"")&&UUID.test(task.run_id||"")&&
  task.source_sha===env.RUNTIME_SOURCE_SHA&&task.deadline>now&&
  ["submitted","running","uploading","link_ready"].includes(task.state),"runtime_task_closed");
 const identity=await verifyCircleJWT(token,{run:task.run_id,job:worker},await fetchKeys(send),now);
 const data=(await publicJSON(send,"https://circleci.com/api/v3/runs/"+task.run_id)).data;
 const refs=data?.references,vcs=refs?.event?.attributes?.vcs;
 need(data?.id===task.run_id&&refs?.project?.id===TRUST.project&&refs?.pipeline?.id===TRUST.definition&&
  vcs?.origin_repository_url==="https://"+TRUST.source&&vcs?.target_repository_url==="https://"+TRUST.source&&
  vcs?.branch===TRUST.ref.slice(11)&&vcs?.revision===task.source_sha&&data?.attributes?.phase!=="ended","runtime_run_binding");
 const workflows=(await publicJSON(send,"https://circleci.com/api/v2/pipeline/"+task.run_id+"/workflow")).items;
 need(Array.isArray(workflows)&&workflows.length===1&&workflows[0].name==="managed-runtime-tasks"&&
  workflows[0].pipeline_id===task.run_id&&UUID.test(workflows[0].id),"runtime_workflow_binding");
 const jobs=(await publicJSON(send,"https://circleci.com/api/v2/workflow/"+workflows[0].id+"/job")).items;
 need(Array.isArray(jobs)&&jobs.length===1&&jobs[0].id===worker&&jobs[0].name==="managed-runtime-task"&&
  jobs[0].status==="running"&&(!task.worker_job_id||task.worker_job_id===worker),"runtime_worker_binding");
 return {...identity,workflow_id:workflows[0].id};
}
export async function githubIdentity(request,env,task,run,now,send){
 const token=request.headers.get("x-ipazake-github-token")||"";
 need(/^[A-Za-z0-9_.-]{100,16384}$/.test(token)&&task.source_sha===env.RUNTIME_SOURCE_SHA&&
  task.deadline>now&&task.worker_job_id&&["running","uploading"].includes(task.state),"publisher_task_closed");
 const identity=await verifyGithubJWT(token,{source:task.source_sha,run,role:"lease"},await fetchGithubKeys(send),now);
 const value=await publicJSON(send,"https://api.github.com/repos/"+GITHUB_TRUST.repository+"/actions/runs/"+run);
 need(value.id===Number(run)&&value.repository?.id===Number(GITHUB_TRUST.repository_id)&&
  value.actor?.id===Number(GITHUB_TRUST.owner_id)&&value.event==="workflow_dispatch"&&value.run_attempt===1&&
  value.head_sha===task.source_sha&&value.head_branch===TRUST.ref.slice(11)&&value.status==="in_progress"&&
  value.path===GITHUB_TRUST.workflows.lease&&value.display_title==="CircleCI lease "+task.job_id,"publisher_run_binding");
 return identity;
}
