import test from "node:test";
import assert from "node:assert/strict";
import {smokeTransfer,quotaStatus,NAME,SIZE} from "./drive-smoke.mjs";
import {SCOPE} from "./drive-auth.mjs";
const env={PILOT_ENABLED:"0",PILOT_LINK_ENABLED:"0",PILOT_DRIVE_CLIENT_ID:"synthetic-client-123.apps.googleusercontent.com",
 PILOT_DRIVE_CLIENT_SECRET:"synthetic-test-only-secret",PILOT_DRIVE_REFRESH_TOKEN:"synthetic-test-only-refresh",PILOT_DRIVE_RECIPIENT_EMAIL:"owner@example.invalid"};
const id="syntheticFileId12345",session="https://www.googleapis.com/upload/drive/v3/files?upload_id=synthetic";
function fake(opts={}){
 let bytes=opts.stored?new TextEncoder().encode(("ipazake free pilot transfer verification; synthetic data only.\n"+"-".repeat(SIZE)).slice(0,SIZE)):undefined;
 let metadata=opts.stored?{appProperties:{pilot_fixture:"free-pilot-smoke-v1"}}:undefined;
 const calls=[];
 return {calls,send:async(url,init={})=>{
   calls.push([url,init.method||"GET"]);assert.equal(init.redirect,"manual");assert.ok(init.signal instanceof AbortSignal);
   if(url==="https://oauth2.googleapis.com/token")return Response.json({access_token:"synthetic-issued-access-token",token_type:"Bearer",expires_in:3600,scope:SCOPE});
   assert.equal(new URL(url).origin,"https://www.googleapis.com");
   if(url.includes("/about?")){
     assert.equal(init.method,"GET");assert.equal(new URL(url).searchParams.get("fields"),"user(emailAddress),storageQuota(limit,usage)");
     if(opts.aboutStatus)return Response.json({error:{message:"synthetic provider error"}},{status:opts.aboutStatus});
     return Response.json({user:{emailAddress:opts.email||env.PILOT_DRIVE_RECIPIENT_EMAIL},storageQuota:opts.noQuota?{}:{limit:String(opts.limit??15*1024**3),usage:String(opts.usage||0)}});
   }
   if(url.includes("/files?")&&url.includes("q="))return Response.json({files:opts.stored?[{id}]:[]});
   if(url.includes("/generateIds?"))return Response.json({ids:[id]});
   if(url.includes("uploadType=resumable")){
     metadata=JSON.parse(init.body);assert.equal(metadata.id,id);assert.equal(metadata.name,NAME);assert.equal(metadata.appProperties.pilot_fixture,"free-pilot-smoke-v1");
     return new Response(null,{headers:{Location:opts.badSession?"https://example.invalid/upload":session}});
   }
   if(url===session){bytes=init.body;assert.equal(bytes.length,SIZE);assert.equal(init.headers["Content-Range"],"bytes 0-1023/1024");if(opts.badUpload)throw Error("synthetic interrupted upload");return Response.json({id})}
   if(url.includes("/permissions?"))return Response.json({permissions:opts.public?[{type:"anyone",role:"reader"}]:[{type:"user",role:"owner",emailAddress:env.PILOT_DRIVE_RECIPIENT_EMAIL}]});
   if(url.includes("?alt=media"))return new Response(opts.corrupt?new Uint8Array(SIZE):bytes);
   if(url.includes("/files/"+id+"?")){
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),n=>n.toString(16).padStart(2,"0")).join("");
      return Response.json({...metadata,id,name:NAME,sha256Checksum:hash,size:String(SIZE),trashed:false,ownedByMe:true,mimeType:"application/octet-stream",...opts.metadata});
   }
   throw Error("unexpected endpoint");
 }};
}
test("one fixed synthetic upload with private ACL and exact SHA-256 round trip",async()=>{
 const f=fake(),r=await smokeTransfer(env,f.send);assert.equal(r.ok,true);assert.equal(r.bytes,SIZE);assert.equal(r.owner_only,true);assert.equal(r.created,true);assert.match(r.sha256,/^[a-f0-9]{64}$/);
 assert.equal(f.calls.filter(([u,m])=>m==="PUT").length,1);
});
test("no provider call if active switches or incomplete auth",async()=>{
 const f=fake();assert.equal((await smokeTransfer({...env,PILOT_ENABLED:"1"},f.send)).ok,false);assert.equal(f.calls.length,0);
});
test("quota, untrusted session, interrupted upload, public ACL and corrupt media fail closed",async()=>{
 for(const [opts,stage,mayExist] of [[{usage:15*1024**3},"quota_insufficient",false],[{badSession:true},"upload_start",false],[{badUpload:true},"upload",true],[{public:true},"acl",true],[{corrupt:true},"download",true]]){
   const f=fake(opts),r=await smokeTransfer(env,f.send);assert.deepEqual(r,{ok:false,stage,upload_may_exist:mayExist});
   assert.ok(f.calls.filter(([u,m])=>m==="PUT").length<=1);
 }
});

test("read-only eligibility failures are distinct and never proceed to file creation",async()=>{
 for(const [opts,stage] of [
   [{aboutStatus:403},"quota_api_forbidden"],[{aboutStatus:401},"quota_api_unauthorized"],
   [{aboutStatus:429},"quota_api_limited"],[{aboutStatus:500},"quota_api_unavailable"],
   [{email:"different@example.invalid"},"account_mismatch"],[{noQuota:true},"quota_unavailable"],
   [{limit:16*1024**3},"quota_not_free_compatible"],[{usage:15*1024**3},"quota_insufficient"]
 ]){
   const f=fake(opts);
   assert.deepEqual(await smokeTransfer(env,f.send),{ok:false,stage,upload_may_exist:false});
   assert.equal(f.calls.length,2);
 }
});
test("free quota boundary is exact and malformed values fail closed",()=>{
 const email="owner@example.invalid",limit=15*1024**3;
 const val=usage=>({user:{emailAddress:email},storageQuota:{limit:String(limit),usage:String(usage)}});
 assert.equal(quotaStatus(val(limit-1000000000-SIZE),email),"ok");
 assert.equal(quotaStatus(val(limit-1000000000-SIZE+1),email),"quota_insufficient");
 assert.equal(quotaStatus(val(limit+1),email),"quota_unavailable");
 assert.equal(quotaStatus(val(-1),email),"quota_unavailable");
 assert.equal(quotaStatus(null,email),"account_mismatch");
});

test("read-only check verifies an existing fixture without making any Drive writes",async()=>{
 const f=fake({stored:true,metadata:{mimeType:"text/plain"}});
 const r=await smokeTransfer(env,f.send,{allowCreate:false});
 assert.equal(r.ok,true);
 assert.equal(r.created,false);
 assert.equal(r.owner_only,true);
 assert.ok(f.calls.filter(([u])=>new URL(u).hostname==="www.googleapis.com").every(([,method])=>method==="GET"));
});

test("read-only check stops before reserving an ID if the fixture is missing",async()=>{
 const f=fake();
 const r=await smokeTransfer(env,f.send,{allowCreate:false});
 assert.deepEqual(r,{ok:false,stage:"fixture_missing",upload_may_exist:false});
 assert.equal(f.calls.length,3);
});

test("read-only metadata checks report a safe failure category before downloading",async()=>{
 for(const [metadata,stage] of [
   [{appProperties:{}},"metadata_identity"],
   [{ownedByMe:false},"metadata_owner"],
   [{size:"0"},"metadata_size"],
   [{sha256Checksum:undefined},"metadata_digest_missing"],
   [{sha256Checksum:"0".repeat(64)},"metadata_digest_mismatch"],
   [{mimeType:"text/html"},"metadata_mime"],
   [{resourceKey:"synthetic"},"metadata_resource_key"],
 ]){
   const f=fake({stored:true,metadata});
   assert.deepEqual(await smokeTransfer(env,f.send,{allowCreate:false}),{ok:false,stage,upload_may_exist:false});
   assert.ok(!f.calls.some(([u])=>u.includes("alt=media")||u.includes("uploadType")));
 }
});

test("private link check uses the existing fixture and returns only a sanitized result",async()=>{
 const f=fake({stored:true,metadata:{mimeType:"text/plain"}});
 const r=await smokeTransfer(env,f.send,{allowCreate:false,verifyLink:true});
 assert.equal(r.ok,true);
 assert.equal(r.private_link_verified,true);
 assert.equal(r.created,false);
 assert.equal(f.calls.filter(([url])=>url.includes("/permissions?")).length,2);
 assert.ok(f.calls.filter(([url])=>new URL(url).hostname==="www.googleapis.com").every(([,method])=>method==="GET"));
 assert.ok(!JSON.stringify(r).includes(id));
 const blocked=fake();
 assert.deepEqual(await smokeTransfer(env,blocked.send,{verifyLink:true}),{ok:false,stage:"configuration",upload_may_exist:false});
 assert.equal(blocked.calls.length,0);
});
