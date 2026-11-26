import test from "node:test";
import assert from "node:assert/strict";
import {webcrypto} from "node:crypto";
import {TRUST,verifyCircleJWT,fetchKeys} from "./oidc.mjs";
globalThis.crypto??=webcrypto;
const pair=await crypto.subtle.generateKey({name:"RSASSA-PKCS1-v1_5",modulusLength:2048,
  publicExponent:new Uint8Array([1,0,1]),hash:"SHA-256"},true,["sign","verify"]);
const jwk=await crypto.subtle.exportKey("jwk",pair.publicKey);jwk.kid="fixture";
const keys={keys:[jwk]},now=1795696000;
const expected={run:"12345678-1234-1234-1234-123456789abc",job:"23456789-1234-1234-1234-123456789abc"};
const base={iss:"https://oidc.circleci.com/org/"+TRUST.org,aud:TRUST.org,iat:now-60,exp:now+300,
  sub:"org:"+TRUST.org+":project:"+TRUST.project+":user:"+TRUST.user+
    ":checkout-source:"+TRUST.source+":checkout-ref:"+TRUST.ref+
    ":config-source:"+TRUST.source+":config-ref:"+TRUST.ref};
for(const [key,value] of Object.entries({"org-id":TRUST.org,"project-id":TRUST.project,
  "pipeline-id":TRUST.definition,"run-id":expected.run,"job-id":expected.job,"ssh-rerun":false,
  "checkout-source":TRUST.source,"config-source":TRUST.source,"checkout-ref":TRUST.ref,
  "config-ref":TRUST.ref,"context-ids":[]}))base["oidc.circleci.com/"+key]=value;
const enc=value=>Buffer.from(value).toString("base64url");
async function signed(changes={},head={}){
  const input=enc(JSON.stringify({alg:"RS256",kid:"fixture",typ:"JWT",...head}))+"."+
    enc(JSON.stringify({...base,...changes}));
  return input+"."+enc(await crypto.subtle.sign("RSASSA-PKCS1-v1_5",pair.privateKey,new TextEncoder().encode(input)));
}
test("valid signed identity is bound to exact run and job",async()=>{
  assert.equal((await verifyCircleJWT(await signed(),expected,keys,now)).verified,true);
});
test("tampered signature and missing key refused",async()=>{
  const token=await signed();const p=token.split(".");
  p[1]=enc(JSON.stringify({...base,exp:now+600}));
  await assert.rejects(verifyCircleJWT(p.join("."),expected,keys,now),/signature/);
  await assert.rejects(verifyCircleJWT(token,expected,{keys:[]},now),/key/);
});
test("algorithm and remote key injection refused",async()=>{
  for(const h of [{alg:"none"},{alg:"HS256"},{jku:"https://evil.invalid/keys"},{jwk},{crit:["x"]}])
    await assert.rejects(verifyCircleJWT(await signed({},h),expected,keys,now),/header/);
});
test("wrong issuer, audience, expiry and future token refused",async()=>{
  for(const c of [{iss:"https://evil.invalid"},{aud:"other"},{exp:now},{iat:now+61,exp:now+600},
    {iat:now-4000,exp:now+100},{exp:now+5000},{nbf:now+100}])
    await assert.rejects(verifyCircleJWT(await signed(c),expected,keys,now));
});
test("foreign config, branch, checkout and SSH rerun refused",async()=>{
  for(const [key,value] of Object.entries({"config-source":"github.com/foreign/repo",
    "config-ref":"refs/heads/main","checkout-source":"github.com/foreign/repo",
    "checkout-ref":"refs/heads/main","ssh-rerun":true,"project-id":expected.run,
    "pipeline-id":expected.run,"run-id":expected.job,"job-id":expected.run})){
    await assert.rejects(verifyCircleJWT(await signed({["oidc.circleci.com/"+key]:value}),expected,keys,now));
  }
});
test("wrong subject and malformed token refused",async()=>{
  await assert.rejects(verifyCircleJWT(await signed({sub:"other"}),expected,keys,now),/subject/);
  for(const raw of ["", "a.b", "a.b.c.d", "a".repeat(16385)])
    await assert.rejects(verifyCircleJWT(raw,expected,keys,now));
});
test("key fetch uses fixed public origin, no authentication and no redirects",async()=>{
  let called=false;
  const value=await fetchKeys(async(url,options)=>{
    called=true;assert.equal(url,"https://oidc.circleci.com/org/"+TRUST.org+"/.well-known/jwks.json");
    assert.equal(options.redirect,"error");assert.deepEqual(options.headers,{accept:"application/json"});
    return new Response(JSON.stringify(keys));
  });
  assert.ok(called);assert.equal(value.keys.length,1);
});
