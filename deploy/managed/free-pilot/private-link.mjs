// Restricted Drive link pilot for files already deposited by an authorized operator.
// No file uploads, public shares, billing APIs or arbitrary origins.
import {authMode,accessForRequest,googleFetch} from "./drive-auth.mjs";
const FILE=/^[A-Za-z0-9_-]{10,160}$/;
const JOB=/^pilot_[a-f0-9]{32}$/;
const HASH=/^[a-f0-9]{64}$/;
const EMAIL=/^[^\s@]{1,128}@[^\s@]{1,128}$/;
export const MAX=10_000_000_000;
export const WINDOW=7200;
export const RETENTION_GRACE=86400;
export const LINK_SQL={
  register:`INSERT INTO pilot_links(job_id,owner_id,file_id,filename,bytes,sha256,expires_at)
    SELECT job_id,owner_id,?,?,?,?,? FROM pilot_jobs
    WHERE job_id=? AND owner_id=? AND state='waiting_for_runtime'
    ON CONFLICT(job_id) DO NOTHING`,
  lookup:`SELECT l.file_id,l.filename,l.bytes,l.sha256,l.expires_at
    FROM pilot_links l JOIN pilot_jobs j ON j.job_id=l.job_id AND j.owner_id=l.owner_id
    WHERE l.job_id=? AND l.owner_id=? AND j.state='waiting_for_runtime' AND l.expires_at>? AND l.retired_at IS NULL`,
  retire:`UPDATE pilot_links SET retired_at=COALESCE(retired_at,?)
    WHERE job_id=? AND owner_id=? AND file_id=? AND filename=? AND bytes=? AND sha256=? AND expires_at<=?`
};
function need(ok){if(!ok)throw Error("private_link_unavailable");}
export function metadata(value){
  need(value&&typeof value==="object"&&!Array.isArray(value)&&
    typeof value.file_id==="string"&&FILE.test(value.file_id)&&typeof value.sha256==="string"&&HASH.test(value.sha256)&&
    Number.isSafeInteger(value.bytes)&&value.bytes>0&&value.bytes<=MAX&&
    typeof value.filename==="string"&&value.filename.length<=160&&
    /^[\p{L}\p{N} ._()\-]+\.(?:ipa|zip|bin|txt)$/iu.test(value.filename)&&
    !value.filename.startsWith("."));
  return {file_id:value.file_id,filename:value.filename,bytes:value.bytes,sha256:value.sha256};
}
export function configured(env){
  return env.PILOT_LINK_ENABLED==="1"&&authMode(env)!==null&&
    typeof env.PILOT_DRIVE_RECIPIENT_EMAIL==="string"&&EMAIL.test(env.PILOT_DRIVE_RECIPIENT_EMAIL);
}
async function api(path,accessToken,send){
  const reply=await send("https://www.googleapis.com/drive/v3/"+path,{
    method:"GET",redirect:"manual",signal:AbortSignal.timeout(10000),headers:{
      Authorization:"Bearer "+accessToken,Accept:"application/json"
    }});
  if(reply.status!==200){if(reply.body)await reply.body.cancel();throw Error("private_link_unavailable");}
  const reader=reply.body?.getReader();
  need(reader);
  let size=0;const parts=[];
  try{
    for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;
      if(size>32768){await reader.cancel();throw Error("private_link_unavailable");}parts.push(value);}
  }finally{reader.releaseLock();}
  const bytes=new Uint8Array(size);let at=0;
  for(const part of parts){bytes.set(part,at);at+=part.byteLength;}
  const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));
  need(value&&typeof value==="object"&&!Array.isArray(value));return value;
}
export async function verifyDrive(value,env,send=googleFetch){
  try{
    need(configured(env));
    const record=metadata(value);
    const accessToken=await accessForRequest(env,send);
    const base="files/"+encodeURIComponent(record.file_id);
    const file=await api(base+"?fields=id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey",accessToken,send);
    need(file.id===record.file_id&&file.name===record.filename&&file.size===String(record.bytes)&&
      file.sha256Checksum===record.sha256&&file.trashed===false&&file.ownedByMe===true&&
      typeof file.mimeType==="string"&&!file.mimeType.startsWith("application/vnd.google-apps.")&&
      !file.resourceKey);
    const access=await api(base+"/permissions?pageSize=100&fields=nextPageToken,permissions(type,role,emailAddress,deleted,expirationTime)",accessToken,send);
    need(!access.nextPageToken&&Array.isArray(access.permissions)&&access.permissions.length>=1&&access.permissions.length<=2);
    const email=env.PILOT_DRIVE_RECIPIENT_EMAIL.toLowerCase();
    let owners=0,recipient=0;
    for(const p of access.permissions){
      need(p&&p.type==="user"&&!p.deleted&&typeof p.emailAddress==="string"&&EMAIL.test(p.emailAddress));
      const match=p.emailAddress.toLowerCase()===email;
      // Only an owning account and the designated reader may access this file.
      if(p.role==="owner"){owners++;if(match)recipient++;}
      else {need(p.role==="reader"&&match);recipient++;}
      if(p.expirationTime)need(Number.isFinite(Date.parse(p.expirationTime))&&Date.parse(p.expirationTime)>Date.now());
    }
    need(owners===1&&recipient===1);
    return "https://drive.google.com/file/d/"+record.file_id+"/view";
  }catch{throw Error("private_link_unavailable");}
}
export async function registerLink(db,owner,value,env,now,send=googleFetch){
  need(value&&Object.keys(value).sort().join(",")==="bytes,file_id,filename,job_id,sha256"&&JOB.test(value.job_id));
  const record=metadata(value);
  // No readiness assertion until provider metadata and restricted ACL are checked.
  await verifyDrive(record,env,send);
  const result=await db.prepare(LINK_SQL.register).bind(record.file_id,record.filename,record.bytes,record.sha256,now+WINDOW,value.job_id,owner).run();
  need(result.success===true&&[0,1].includes(result.meta?.changes));
  return result.meta.changes===1;
}
export async function getLink(db,owner,id,env,now,send=googleFetch){
  need(JOB.test(id)&&configured(env));
  const row=await db.prepare(LINK_SQL.lookup).bind(id,owner,now).first();
  if(!row)return null;
  need(Number.isSafeInteger(row.expires_at)&&row.expires_at>now&&row.expires_at<=now+WINDOW);
  const record=metadata(row);
  const url=await verifyDrive(record,env,send);
  // Drive's ACL is checked again before returning a link. The bot's expiry is NOT a Drive ACL expiry.
  return {...record,url,expires_at:row.expires_at};
}

export async function retireLink(db,owner,value,now){
  need(value&&Object.keys(value).sort().join(",")==="bytes,file_id,filename,job_id,sha256"&&typeof value.job_id==="string"&&JOB.test(value.job_id));
  const record=metadata(value);
  // Idempotent exact-receipt retirement, only after expiration plus a full day.
  // Never delete provider files from this Worker.
  const result=await db.prepare(LINK_SQL.retire).bind(now,value.job_id,owner,record.file_id,record.filename,record.bytes,record.sha256,now-RETENTION_GRACE).run();
  need(result.success===true&&[0,1].includes(result.meta?.changes));
  return result.meta.changes===1;
}
