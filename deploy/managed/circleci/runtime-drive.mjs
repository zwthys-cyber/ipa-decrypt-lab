import {accessForRequest} from "../free-pilot/drive-auth.mjs";
import {need} from "./runtime-auth.mjs";
const EMAIL=/^[^\s@]{1,128}@[^\s@]{1,128}$/;
function allowed(task,env){
 const fixture=env.RUNTIME_MODE==="staging"&&task.kind==="fixture"&&task.drive_fixture===1&&task.fixture_authorized===1;
 const real=env.RUNTIME_MODE==="production"&&task.kind==="export";
 need((fixture||real)&&["uploading","link_ready","completed"].includes(task.state)&&
  /^[a-f0-9]{64}$/.test(task.plaintext_sha256||"")&&Number.isSafeInteger(task.plaintext_bytes)&&
  task.plaintext_bytes>0&&task.plaintext_bytes<=2000000000&&EMAIL.test(env.PILOT_DRIVE_RECIPIENT_EMAIL||""),
  "runtime_drive_not_authorized");
}
async function get(path,token,send){
 const reply=await send("https://www.googleapis.com/drive/v3/"+path,{method:"GET",redirect:"manual",
  signal:AbortSignal.timeout(10000),headers:{authorization:"Bearer "+token,accept:"application/json"}});
 need(reply.status===200,"runtime_drive_metadata");
 const text=await reply.text();need(text.length<=32768,"runtime_drive_limit");return JSON.parse(text);
}
function decimal(value){
 need(typeof value==="string"&&/^[0-9]{1,20}$/.test(value),"runtime_drive_quota");
 const result=Number(value);need(Number.isSafeInteger(result),"runtime_drive_quota");return result;
}
export async function uploadAccess(task,env,now,send){
 allowed(task,env);need(["uploading","link_ready"].includes(task.state),"runtime_drive_write_closed");const token=await accessForRequest(env,send);
 const about=await get("about?fields=storageQuota(limit,usage),user(emailAddress)",token,send);
 need(typeof about?.user?.emailAddress==="string"&&
  about.user.emailAddress.toLowerCase()===env.PILOT_DRIVE_RECIPIENT_EMAIL.toLowerCase(),"runtime_drive_owner");
 const limit=decimal(about.storageQuota?.limit),usage=decimal(about.storageQuota?.usage);
 need(limit>0&&limit<=15*1024**3&&usage<=limit&&limit-usage>=task.plaintext_bytes+1000000000,
  "runtime_drive_free_storage");
 return {access_token:token,recipient_email:env.PILOT_DRIVE_RECIPIENT_EMAIL.toLowerCase(),refresh_after:now+60};
}
export async function verifyOwnedUpload(task,record,env,send){
 allowed(task,env);
 need(record&&Object.keys(record).sort().join(",")==="bytes,file_id,filename,sha256"&&
  /^[A-Za-z0-9_-]{10,160}$/.test(record.file_id||"")&&record.filename===task.filename&&
  record.bytes===task.plaintext_bytes&&record.sha256===task.plaintext_sha256,"runtime_drive_binding");
 const token=await accessForRequest(env,send);
 const id=encodeURIComponent(record.file_id);
 const file=await get("files/"+id+"?fields=id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey",token,send);
 need(file.id===record.file_id&&file.name===record.filename&&file.size===String(record.bytes)&&
  file.sha256Checksum===record.sha256&&file.trashed===false&&file.ownedByMe===true&&
  typeof file.mimeType==="string"&&!file.mimeType.startsWith("application/vnd.google-apps.")&&!file.resourceKey,
  "runtime_drive_integrity");
 const access=await get("files/"+id+"/permissions?pageSize=100&fields=nextPageToken,permissions(type,role,emailAddress,deleted)",token,send);
 need(!access.nextPageToken&&Array.isArray(access.permissions)&&access.permissions.length===1,"runtime_drive_private_acl");
 const owner=access.permissions[0];
 need(owner?.type==="user"&&owner.role==="owner"&&owner.deleted!==true&&typeof owner.emailAddress==="string"&&
  owner.emailAddress.toLowerCase()===env.PILOT_DRIVE_RECIPIENT_EMAIL.toLowerCase(),"runtime_drive_private_acl");
 return {file_id:record.file_id,filename:record.filename,bytes:record.bytes,sha256:record.sha256};
}

export async function cleanupFixture(task,env,now,send){
 need(env.RUNTIME_MODE==="staging"&&task.kind==="fixture"&&task.drive_fixture===1&&
  task.fixture_authorized===1&&task.state==="link_ready","runtime_fixture_cleanup_only");
 const record={file_id:task.file_id,filename:task.filename,bytes:task.plaintext_bytes,sha256:task.plaintext_sha256};
 const saved=await env.DB.prepare("SELECT * FROM runtime_drive_fixtures WHERE job_id=?").bind(task.job_id).first();
 need(saved?.file_id===record.file_id,"runtime_fixture_cleanup_binding");
 if(saved.cleanup_state==="confirmed")return true;
 const token=await accessForRequest(env,send),url="https://www.googleapis.com/drive/v3/files/"+encodeURIComponent(record.file_id);
 if(saved.cleanup_state==="waiting"){
  await verifyOwnedUpload(task,record,env,send);
  const intent=await env.DB.prepare("UPDATE runtime_drive_fixtures SET cleanup_state='intent' WHERE job_id=? AND file_id=? AND cleanup_state='waiting'")
   .bind(task.job_id,record.file_id).run();
  need(intent.success===true,"runtime_fixture_cleanup_storage");
  if(intent.meta?.changes===1){
   try{
    const response=await send(url,{method:"DELETE",redirect:"manual",signal:AbortSignal.timeout(10000),
     headers:{authorization:"Bearer "+token}});
    if(response.body)await response.body.cancel();
   }catch{}
  }
 }
 // Unknown deletion is read back using the same immutable ID; it never creates another upload.
 const check=await send(url+"?fields=id,trashed",{method:"GET",redirect:"manual",signal:AbortSignal.timeout(10000),
  headers:{authorization:"Bearer "+token}});
 if(check.body)await check.body.cancel();
 need(check.status===404,"runtime_fixture_cleanup_unconfirmed");
 const confirmed=await env.DB.prepare("UPDATE runtime_drive_fixtures SET cleanup_state='confirmed' WHERE job_id=? AND file_id=? AND cleanup_state='intent'")
  .bind(task.job_id,record.file_id).run();
 need(confirmed.success===true,"runtime_fixture_cleanup_storage");return true;
}
