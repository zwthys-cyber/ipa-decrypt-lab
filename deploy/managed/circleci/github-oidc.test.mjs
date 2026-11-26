import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {GITHUB_TRUST as T,verifyGithubJWT,fetchGithubKeys} from "./github-oidc.mjs";
globalThis.crypto??=webcrypto;
const pair=await crypto.subtle.generateKey({name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
  publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256"},true,["sign","verify"]);
const jwk=await crypto.subtle.exportKey("jwk",pair.publicKey);jwk.kid="fixture";
const keys={keys:[jwk]},now=100000,expected={source:"a".repeat(40),run:"123456",role:"lease"};
const encode=value=>Buffer.from(value).toString("base64url");
async function signed(changes={},header={}){
  const claims={iss:T.issuer,aud:T.audience,iat:now-30,nbf:now-30,exp:now+270,
    sub:"repo:"+T.repository+":ref:"+T.ref,repository:T.repository,repository_id:T.repository_id,
    repository_owner_id:T.owner_id,actor_id:T.owner_id,ref:T.ref,ref_type:"branch",sha:expected.source,
    workflow_sha:expected.source,workflow_ref:T.repository+"/"+T.workflows.lease+"@"+T.ref,run_id:expected.run,
    run_attempt:"1",runner_environment:"github-hosted",event_name:"workflow_dispatch",...changes};
  const raw=encode(JSON.stringify({alg:"RS256",kid:"fixture",typ:"JWT",...header}))+"."+encode(JSON.stringify(claims));
  return raw+"."+encode(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",pair.privateKey,new TextEncoder().encode(raw)));
}
test("signed publisher binds immutable IDs, workflow, source and first hosted attempt",async()=>{
  assert.equal((await verifyGithubJWT(await signed(),expected,keys,now)).role,"lease");
  assert.equal((await verifyGithubJWT(await signed({job_workflow_ref:T.repository+"/"+T.workflows.lease+"@"+T.ref,
    job_workflow_sha:expected.source,run_id:123456,run_attempt:1}),expected,keys,now)).role,"lease");
  const sub="repo:zwthys-cyber@"+T.owner_id+"/ipa-decrypt-lab@"+T.repository_id+":ref:"+T.ref;
  assert.equal((await verifyGithubJWT(await signed({sub}),expected,keys,now)).verified,true);
});
test("wrong repository, recycled namespace and actor are refused",async()=>{
  for(const changes of [{repository_id:"other"},{repository_owner_id:"other"},{actor_id:"other"},
    {sub:"repo:other/repo:ref:"+T.ref},{repository:"other/repo"}])
    await assert.rejects(verifyGithubJWT(await signed(changes),expected,keys,now));
});
test("wrong source, workflow, branch or delegated job cannot publish",async()=>{
  for(const changes of [{sha:"b".repeat(40)},{workflow_sha:"b".repeat(40)},{ref:"refs/heads/main"},
    {workflow_ref:T.repository+"/"+T.workflows.probe+"@"+T.ref},{job_workflow_ref:"untrusted"}])
    await assert.rejects(verifyGithubJWT(await signed(changes),expected,keys,now));
});
test("rerun, other run, pull request and self-hosted tokens cannot publish",async()=>{
  for(const changes of [{run_attempt:"2"},{run_id:"other"},{event_name:"pull_request"},{runner_environment:"self-hosted"},
    {environment:"production"}])await assert.rejects(verifyGithubJWT(await signed(changes),expected,keys,now));
});
test("expiry, wrong audience and signature substitution are refused",async()=>{
  for(const changes of [{exp:now},{aud:"other"},{iss:"other"},{iat:now-700,exp:now+1}])
    await assert.rejects(verifyGithubJWT(await signed(changes),expected,keys,now));
  const jwt=await signed();await assert.rejects(verifyGithubJWT(jwt.slice(0,-10)+"A".repeat(10),expected,keys,now));
  await assert.rejects(verifyGithubJWT(await signed({}, {jku:"https://untrusted.invalid"}),expected,keys,now));
});
test("a proof workflow never gains a publisher role",async()=>{
  const token=await signed({workflow_ref:T.repository+"/"+T.workflows.probe+"@"+T.ref,event_name:"push"});
  assert.equal((await verifyGithubJWT(token,{...expected,role:"probe"},keys,now)).role,"probe");
  await assert.rejects(verifyGithubJWT(token,expected,keys,now));
});
test("JWKS fetch never follows redirects or receives account credentials",async()=>{
  let calls=0;
  await assert.rejects(fetchGithubKeys(async(url,options)=>{
    calls++;assert.equal(url,T.issuer+"/.well-known/jwks");assert.equal(options.redirect,"manual");
    assert.deepEqual(options.headers,{accept:"application/json"});
    return new Response(null,{status:302,headers:{location:"https://untrusted.invalid"}});
  }));
  assert.equal(calls,1);
});
