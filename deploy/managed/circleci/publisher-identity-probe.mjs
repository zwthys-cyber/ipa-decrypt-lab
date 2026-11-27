// Actual GitHub OIDC proof. No JWT or request token is printed or retained.
import {writeFileSync} from "node:fs";
import {GITHUB_TRUST as T,verifyGithubJWT,fetchGithubKeys} from "./github-oidc.mjs";
let stage="context",observed={};
try{
  if(process.env.GITHUB_ACTIONS!=="true"||process.env.GITHUB_REPOSITORY!==T.repository||
    process.env.GITHUB_REF!==T.ref)throw Error("publisher_probe_context");
  const url=new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);
  if(url.protocol!=="https:"||!url.hostname.endsWith(".actions.githubusercontent.com")||
    url.username||url.password||url.port||url.hash)throw Error("publisher_oidc_endpoint");
  url.searchParams.set("audience",T.audience);
  stage="token_request";
  const response=await fetch(url,{redirect:"error",signal:AbortSignal.timeout(15000),
    headers:{authorization:"Bearer "+process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}});
  if(response.status!==200)throw Error("publisher_oidc_request");
  const raw=await response.text();if(raw.length>32768)throw Error("publisher_oidc_limit");
  const token=JSON.parse(raw).value;
  stage="signature_and_claims";
  const claim=JSON.parse(Buffer.from(token.split(".")[1],"base64url").toString("utf8"));
  observed={ttl_seconds:Number.isSafeInteger(claim.exp)&&Number.isSafeInteger(claim.iat)?claim.exp-claim.iat:null,
    repository_match:claim.repository_id===T.repository_id,owner_match:claim.repository_owner_id===T.owner_id,
    actor_match:claim.actor_id===T.owner_id,source_match:claim.sha===process.env.GITHUB_SHA,
    workflow_source_match:claim.workflow_sha===process.env.GITHUB_SHA,
    workflow_match:claim.workflow_ref===T.repository+"/"+T.workflows.probe+"@"+T.ref,
    hosted:claim.runner_environment==="github-hosted",run_match:String(claim.run_id)===process.env.GITHUB_RUN_ID,
    first_attempt:claim.run_attempt===1||claim.run_attempt==="1",environment_present:!!claim.environment,
    job_workflow_present:!!claim.job_workflow_ref,job_workflow_matches:claim.job_workflow_ref===claim.workflow_ref,
    job_workflow_source_matches:claim.job_workflow_sha===process.env.GITHUB_SHA};
  const identity=await verifyGithubJWT(token,{source:process.env.GITHUB_SHA,run:process.env.GITHUB_RUN_ID,role:"probe"},
    await fetchGithubKeys());
  writeFileSync("publisher-identity-proof.json",JSON.stringify(identity)+"\n",{mode:0o600});
  console.log(JSON.stringify(identity));
}catch(error){
  const code=/^(?:github|publisher)_[a-z_]{1,50}$/.test(error?.message||"")?error.message:"publisher_identity_probe_failed";
  console.error(JSON.stringify({schema:"github-publisher-probe-diagnostic-v1",stage,code,...observed}));process.exitCode=1;
}
