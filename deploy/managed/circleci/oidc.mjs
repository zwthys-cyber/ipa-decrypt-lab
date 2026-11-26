// CircleCI V3 job identity verification. No credentials are released by this module.
export const TRUST=Object.freeze({
  org:"b1307c3e-77f6-4c4a-aa7e-1d1bee294780",
  project:"04ca0b08-bd33-434c-a59c-5f4ca8d18688",
  definition:"ed763fe9-befd-4122-83df-30f5d94bb94b",
  user:"532966ad-3735-4fbf-9bdb-03e7071fab4d",
  source:"github.com/zwthys-cyber/ipa-decrypt-lab",
  ref:"refs/heads/upgrade/managed-runtime-v0.2"
});
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
function require(ok,reason){if(!ok)throw Error(reason);}
function bytes(value){
  require(typeof value==="string"&&value.length>0&&/^[A-Za-z0-9_-]+$/.test(value),"jwt_encoding");
  const raw=atob(value.replaceAll("-","+").replaceAll("_","/"));
  return Uint8Array.from(raw,c=>c.charCodeAt(0));
}
function object(value){
  const parsed=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes(value)));
  require(parsed&&typeof parsed==="object"&&!Array.isArray(parsed),"jwt_object");
  return parsed;
}
export async function fetchKeys(send=fetch){
  const response=await send("https://oidc.circleci.com/org/"+TRUST.org+"/.well-known/jwks.json",
    {redirect:"error",headers:{accept:"application/json"}});
  require(response.status===200,"jwks_unavailable");
  const raw=await response.text();
  require(raw.length<=65536,"jwks_limit");
  return JSON.parse(raw);
}
export async function verifyCircleJWT(token,expected,keys,now=Math.floor(Date.now()/1000)){
  require(typeof token==="string"&&token.length<=16384,"jwt_size");
  require(expected&&UUID.test(expected.run)&&UUID.test(expected.job),"expected_identity");
  const parts=token.split(".");
  require(parts.length===3,"jwt_parts");
  const header=object(parts[0]),claim=object(parts[1]);
  require(header.alg==="RS256"&&typeof header.kid==="string"&&header.kid.length<=200&&
    !header.jku&&!header.jwk&&!header.x5u&&!header.crit,"jwt_header");
  require(keys&&Array.isArray(keys.keys)&&keys.keys.length<=20,"jwks_keys");
  const matches=keys.keys.filter(k=>k.kid===header.kid&&k.kty==="RSA"&&
    (!k.alg||k.alg==="RS256")&&(!k.use||k.use==="sig"));
  require(matches.length===1,"jwks_key_missing_or_ambiguous");
  const key=await crypto.subtle.importKey("jwk",matches[0],
    {name:"RSASSA-PKCS1-v1_5",hash:"SHA-256"},false,["verify"]);
  require(await crypto.subtle.verify("RSASSA-PKCS1-v1_5",key,bytes(parts[2]),
    new TextEncoder().encode(parts[0]+"."+parts[1])),"jwt_signature");
  const issuer="https://oidc.circleci.com/org/"+TRUST.org;
  require(claim.iss===issuer&&(claim.aud===TRUST.org||
    (Array.isArray(claim.aud)&&claim.aud.length===1&&claim.aud[0]===TRUST.org)),"jwt_issuer_audience");
  require(Number.isSafeInteger(now)&&Number.isSafeInteger(claim.iat)&&Number.isSafeInteger(claim.exp)&&
    claim.iat<=now+30&&claim.iat>=now-3600&&claim.exp>now&&claim.exp>claim.iat&&
    claim.exp-claim.iat<=3600&&
    (claim.nbf===undefined||(Number.isSafeInteger(claim.nbf)&&claim.nbf<=now+30)),"jwt_time");
  const field=name=>claim["oidc.circleci.com/"+name];
  require(field("org-id")===TRUST.org&&field("project-id")===TRUST.project&&
    field("pipeline-id")===TRUST.definition&&field("run-id")===expected.run&&
    field("job-id")===expected.job&&field("ssh-rerun")===false,"jwt_job_identity");
  require(field("checkout-source")===TRUST.source&&field("config-source")===TRUST.source&&
    field("checkout-ref")===TRUST.ref&&field("config-ref")===TRUST.ref,"jwt_source");
  const subject="org:"+TRUST.org+":project:"+TRUST.project+":user:"+TRUST.user+
    ":checkout-source:"+TRUST.source+":checkout-ref:"+TRUST.ref+
    ":config-source:"+TRUST.source+":config-ref:"+TRUST.ref;
  require(claim.sub===subject,"jwt_subject");
  require(Array.isArray(field("context-ids"))&&field("context-ids").length<=20&&
    field("context-ids").every(x=>UUID.test(x)),"jwt_contexts");
  return {schema:"circleci-oidc-v3-identity-v1",verified:true,project_id:TRUST.project,
    definition_id:TRUST.definition,run_id:expected.run,job_id:expected.job,source:TRUST.source,ref:TRUST.ref};
}
