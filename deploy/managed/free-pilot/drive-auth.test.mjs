import test from "node:test";
import assert from "node:assert/strict";
import {authMode,accessForRequest,SCOPE} from "./drive-auth.mjs";
import {verifyDrive} from "./private-link.mjs";
const mock={
  PILOT_DRIVE_CLIENT_ID:"synthetic-client-123.apps.googleusercontent.com",
  PILOT_DRIVE_CLIENT_SECRET:"synthetic-test-only-secret",
  PILOT_DRIVE_REFRESH_TOKEN:"synthetic-test-only-refresh",
  PILOT_DRIVE_ACCESS_TOKEN:"synthetic-test-only-manual",
  PILOT_DRIVE_RECIPIENT_EMAIL:"owner@example.invalid",
  PILOT_LINK_ENABLED:"1"
};
const answer={access_token:"synthetic-issued-access-token",token_type:"Bearer",expires_in:3600,scope:SCOPE};
test("manual mode and incomplete refresh settings never silently fall back",async()=>{
  assert.equal(authMode({PILOT_DRIVE_ACCESS_TOKEN:mock.PILOT_DRIVE_ACCESS_TOKEN}),"manual");
  const partial={...mock,PILOT_DRIVE_CLIENT_SECRET:""};
  assert.equal(authMode(partial),null);
  await assert.rejects(accessForRequest(partial,()=>{throw Error("must not run")}),/drive_authorization_unavailable/);
});
test("official refresh request uses only fake credentials in tests",async()=>{
  let calls=0;
  const result=await accessForRequest(mock,async(url,init)=>{
    calls++;
    assert.equal(url,"https://oauth2.googleapis.com/token");
    assert.equal(init.method,"POST");
    assert.equal(init.redirect,"error");
    assert.equal(new URLSearchParams(init.body).get("grant_type"),"refresh_token");
    return Response.json(answer);
  });
  assert.equal(result,answer.access_token);assert.equal(calls,1);
});
test("invalid or broad grants fail closed with no fallback",async()=>{
  for(const value of [
    {...answer,scope:"https://www.googleapis.com/auth/drive"},
    {...answer,scope:undefined},{...answer,expires_in:60},
    {...answer,token_type:"Other"},{...answer,refresh_token:"synthetic-unexpected"},
    {...answer,access_token:"invalid\nvalue"}
  ])await assert.rejects(accessForRequest(mock,async()=>Response.json(value)),/drive_authorization_unavailable/);
  await assert.rejects(accessForRequest(mock,async()=>Response.json({error:"invalid_grant"},{status:400})),/drive_authorization_unavailable/);
  await assert.rejects(accessForRequest(mock,async()=>{throw Error("synthetic upstream details")}),/drive_authorization_unavailable/);
});
test("one request-local token verifies both file and ACL; no refresh for invalid metadata",async()=>{
  const record={file_id:"syntheticFile123",filename:"Example.zip",bytes:10000000000,sha256:"a".repeat(64)};
  let refresh=0,api=0;
  const send=async(url,init)=>{
    if(url==="https://oauth2.googleapis.com/token"){refresh++;return Response.json(answer);}
    api++;
    assert.equal(new URL(url).origin,"https://www.googleapis.com");
    assert.equal(init.headers.Authorization,"Bearer "+answer.access_token);
    if(url.includes("/permissions?"))return Response.json({permissions:[{type:"user",role:"owner",emailAddress:mock.PILOT_DRIVE_RECIPIENT_EMAIL}]});
    return Response.json({id:record.file_id,name:record.filename,size:String(record.bytes),sha256Checksum:record.sha256,trashed:false,ownedByMe:true,mimeType:"application/zip"});
  };
  await assert.rejects(verifyDrive({...record,bytes:10000000001},mock,send));
  assert.equal(refresh,0);
  assert.equal(await verifyDrive(record,mock,send),"https://drive.google.com/file/d/"+record.file_id+"/view");
  assert.deepEqual([refresh,api],[1,2]);
});
