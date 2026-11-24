import test from "node:test";
import assert from "node:assert/strict";
import {smokeTransfer,NAME,SIZE} from "./drive-smoke.mjs";
import {SCOPE} from "./drive-auth.mjs";
const env={PILOT_ENABLED:"0",PILOT_LINK_ENABLED:"0",PILOT_DRIVE_CLIENT_ID:"synthetic-client-123.apps.googleusercontent.com",
 PILOT_DRIVE_CLIENT_SECRET:"synthetic-test-only-secret",PILOT_DRIVE_REFRESH_TOKEN:"synthetic-test-only-refresh",PILOT_DRIVE_RECIPIENT_EMAIL:"owner@example.invalid"};
const id="syntheticFileId12345",session="https://www.googleapis.com/upload/drive/v3/files?upload_id=synthetic";
function fake(opts={}){
 let bytes,metadata,calls=[],stored=opts.stored;
 return {calls,send:async(url,init={})=>{
   calls.push([url,init.method||"GET"]);assert.equal(init.redirect,"manual");assert.ok(init.signal instanceof AbortSignal);
   if(url==="https://oauth2.googleapis.com/token")return Response.json({access_token:"synthetic-issued-access-token",token_type:"Bearer",expires_in:3600,scope:SCOPE});
   assert.equal(new URL(url).origin,"https://www.googleapis.com");
   if(url.includes("/about?"))return Response.json({user:{emailAddress:env.PILOT_DRIVE_RECIPIENT_EMAIL},storageQuota:{limit:String(15*1024**3),usage:String(opts.usage||0)}});
   if(url.includes("/files?")&&url.includes("q="))return Response.json({files:[]});
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
      return Response.json({...metadata,id,name:NAME,sha256Checksum:hash,size:String(SIZE),trashed:false,ownedByMe:true,mimeType:"application/octet-stream"});
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
 for(const [opts,stage,mayExist] of [[{usage:15*1024**3},"quota",false],[{badSession:true},"upload_start",false],[{badUpload:true},"upload",true],[{public:true},"acl",true],[{corrupt:true},"download",true]]){
   const f=fake(opts),r=await smokeTransfer(env,f.send);assert.deepEqual(r,{ok:false,stage,upload_may_exist:mayExist});
   assert.ok(f.calls.filter(([u,m])=>m==="PUT").length<=1);
 }
});
