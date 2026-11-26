// Distinct GitHub publisher role. CircleCI tokens cannot authenticate these endpoints.
export const GITHUB_TRUST=Object.freeze({
  issuer:"https://token.actions.githubusercontent.com",repository:"zwthys-cyber/ipa-decrypt-lab",
  repository_id:"1444792484",owner_id:"246379322",ref:"refs/heads/upgrade/managed-runtime-v0.2",
  audience:"https://ipazake-free-control-pilot.hahayesadd.workers.dev",
  workflows:{lease:".github/workflows/circleci-secret-lease.yml",probe:".github/workflows/circleci-publisher-identity.yml"}
});
function require(value,code){if(!value)throw Error(code);}
function bytes(value){
  require(typeof value==="string"&&/^[A-Za-z0-9_-]+$/.test(value),"github_jwt_encoding");
  return Uint8Array.from(atob(value.replaceAll("-","+").replaceAll("_","/")),c=>c.charCodeAt(0));
}
function object(raw){
  const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes(raw)));
  require(value&&typeof value==="object"&&!Array.isArray(value),"github_jwt_object");return value;
}
export async function fetchGithubKeys(send=(url,init)=>globalThis.fetch(url,init)){
  const reply=await send(GITHUB_TRUST.issuer+"/.well-known/jwks",
    {redirect:"manual",signal:AbortSignal.timeout(10000),headers:{accept:"application/json"}});
  require(reply.status===200,"github_jwks_unavailable");
  const text=await reply.text();require(text.length<=65536,"github_jwks_limit");return JSON.parse(text);
}
export async function verifyGithubJWT(token,expected,keys,now=Math.floor(Date.now()/1000)){
  require(typeof token==="string"&&token.length<=16384,"github_jwt_size");
  require(expected&&/^[a-f0-9]{40}$/.test(expected.source||"")&&/^[1-9][0-9]{0,19}$/.test(expected.run||"")&&
    ["lease","probe"].includes(expected.role),"github_expected_identity");
  const parts=token.split(".");require(parts.length===3,"github_jwt_parts");
  const header=object(parts[0]),claim=object(parts[1]);
  require(header.alg==="RS256"&&typeof header.kid==="string"&&header.kid.length<=200&&
    !header.jku&&!header.jwk&&!header.x5u&&!header.crit,"github_jwt_header");
  require(keys&&Array.isArray(keys.keys)&&keys.keys.length<=20,"github_jwks_shape");
  const found=keys.keys.filter(k=>k.kid===header.kid&&k.kty==="RSA"&&(!k.alg||k.alg==="RS256")&&(!k.use||k.use==="sig"));
  require(found.length===1,"github_jwk_identity");
  const key=await crypto.subtle.importKey("jwk",found[0],{name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  require(await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,bytes(parts[2]),
    new TextEncoder().encode(parts[0]+"."+parts[1])),"github_jwt_signature");
  const t=GITHUB_TRUST;
  require(claim.iss===t.issuer&&claim.aud===t.audience,"github_jwt_issuer_audience");
  require(Number.isSafeInteger(now)&&Number.isSafeInteger(claim.iat)&&Number.isSafeInteger(claim.exp)&&
    claim.iat>=now-600&&claim.iat<=now+30&&claim.exp>now&&claim.exp>claim.iat&&claim.exp-claim.iat<=600&&
    Number.isSafeInteger(claim.nbf)&&claim.nbf<=now+30,"github_jwt_time");
  const subject="repo:"+t.repository+":ref:"+t.ref;
  const immutable="repo:zwthys-cyber@"+t.owner_id+"/ipa-decrypt-lab@"+t.repository_id+":ref:"+t.ref;
  require([subject,immutable].includes(claim.sub)&&claim.repository===t.repository&&claim.repository_id===t.repository_id&&
    claim.repository_owner_id===t.owner_id&&claim.actor_id===t.owner_id,"github_jwt_repository");
  require(claim.ref===t.ref&&claim.ref_type==="branch"&&claim.sha===expected.source&&claim.workflow_sha===expected.source&&
    claim.workflow_ref===t.repository+"/"+t.workflows[expected.role]+"@"+t.ref,"github_jwt_source");
  require(claim.run_id===expected.run&&claim.run_attempt==="1"&&claim.runner_environment==="github-hosted"&&
    !claim.environment&&!claim.job_workflow_ref&&!claim.job_workflow_sha,"github_jwt_run");
  require(expected.role==="lease"?claim.event_name==="workflow_dispatch":
    ["push","workflow_dispatch"].includes(claim.event_name),"github_jwt_event");
  return {schema:"github-publisher-identity-v1",verified:true,role:expected.role,run_id:expected.run,
    source_sha:expected.source,repository_id:t.repository_id};
}
