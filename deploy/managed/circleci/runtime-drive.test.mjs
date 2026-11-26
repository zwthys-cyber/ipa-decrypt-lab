import test from "node:test";
import assert from "node:assert/strict";
import {uploadAccess,verifyOwnedUpload} from "./runtime-drive.mjs";
const task={kind:"fixture",drive_fixture:1,fixture_authorized:1,state:"uploading",
 plaintext_sha256:"a".repeat(64),plaintext_bytes:5496,filename:"Fixture.ipa"};
const env={RUNTIME_MODE:"staging",PILOT_DRIVE_RECIPIENT_EMAIL:"fixture@example.invalid",PILOT_DRIVE_ACCESS_TOKEN:"T".repeat(32)};
const record={file_id:"FIXTURE_FILE_12345",filename:task.filename,bytes:task.plaintext_bytes,sha256:task.plaintext_sha256};
function provider(change={}){
 return async(url,init)=>{
  assert.equal(init.redirect,"manual");assert.equal(init.method,"GET");
  assert.equal(init.headers.authorization,"Bearer "+env.PILOT_DRIVE_ACCESS_TOKEN);
  if(url.includes("about?"))return Response.json({storageQuota:{limit:String(15*1024**3),usage:"0"},user:{emailAddress:env.PILOT_DRIVE_RECIPIENT_EMAIL},...change});
  if(url.includes("/permissions?"))return Response.json({permissions:[{type:"user",role:"owner",emailAddress:env.PILOT_DRIVE_RECIPIENT_EMAIL}],...change});
  return Response.json({id:record.file_id,name:record.filename,size:String(record.bytes),sha256Checksum:record.sha256,
   ownedByMe:true,trashed:false,mimeType:"application/octet-stream",...change});
 };
}
test("request-local access requires explicit fixture authorization and owner quota",async()=>{
 assert.equal((await uploadAccess(task,env,100,provider())).refresh_after,160);
 for(const changed of [{fixture_authorized:0},{drive_fixture:0},{kind:"export"},{state:"cancelled"},{plaintext_bytes:2000000001}])
  await assert.rejects(uploadAccess({...task,...changed},env,100,provider()),/authorized/);
 await assert.rejects(uploadAccess(task,env,100,provider({user:{emailAddress:"other@example.invalid"}})),/owner/);
 for(const storageQuota of [{limit:String(100*1024**3),usage:"0"},{limit:"1000",usage:"0"},{usage:"0"},{limit:String(15*1024**3),usage:String(15*1024**3)}])
  await assert.rejects(uploadAccess(task,env,100,provider({storageQuota})));
});
test("registration independently verifies checksum, name, size and sole owner ACL",async()=>{
 assert.deepEqual(await verifyOwnedUpload(task,record,env,provider()),record);
 for(const changed of [{sha256Checksum:"b".repeat(64)},{name:"Other.ipa"},{size:"5497"},{ownedByMe:false},{trashed:true},
  {resourceKey:"shared"},{mimeType:"application/vnd.google-apps.document"},
  {permissions:[{type:"anyone",role:"reader"}]},{nextPageToken:"more"}])
  await assert.rejects(verifyOwnedUpload(task,record,env,provider(changed)));
});
