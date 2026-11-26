import {need} from "./runtime-auth.mjs";
const SHA=/^[a-f0-9]{64}$/;
const canonical=value=>JSON.stringify(Object.fromEntries(Object.keys(value).sort().map(k=>[k,value[k]])));
export async function requestRuntimeLease(db,task,value,now){
 need(task.worker_job_id&&task.state==="running"&&/^age1[0-9a-z]{58}$/.test(value.recipient||"")&&
  /^[a-f0-9]{32}$/.test(value.nonce||"")&&Number.isSafeInteger(value.expires_at)&&
  now<value.expires_at&&value.expires_at<=now+600,"runtime_lease_request");
 const context={schema:"circleci-credential-request-v1",job_id:task.job_id,run_id:task.run_id,
  worker_job_id:task.worker_job_id,source_sha:task.source_sha,profile:task.kind==="fixture"?"synthetic":task.profile+(task.kind==="catalog"?"_catalog":""),
  recipient:value.recipient,nonce:value.nonce,expires_at:value.expires_at};
 const encoded=canonical(context);
 const result=await db.prepare(`INSERT INTO runtime_credential_leases(job_id,context_json,expires_at)
  VALUES(?,?,?) ON CONFLICT(job_id) DO NOTHING`).bind(task.job_id,encoded,value.expires_at).run();
 need(result.success===true,"runtime_lease_storage");
 const saved=await db.prepare("SELECT * FROM runtime_credential_leases WHERE job_id=?").bind(task.job_id).first();
 need(saved?.context_json===encoded&&saved.consumed_at===null&&saved.expires_at>now,"runtime_lease_immutable");
 return context;
}
export async function pendingRuntimeLease(db,task,publisher,now){
 const saved=await db.prepare("SELECT * FROM runtime_credential_leases WHERE job_id=?").bind(task.job_id).first();
 need(saved&&saved.expires_at>now&&saved.consumed_at===null&&
  (!saved.publisher_run_id||saved.publisher_run_id===publisher),"runtime_publisher_bound");
 const result=await db.prepare(`UPDATE runtime_credential_leases SET publisher_run_id=?
  WHERE job_id=? AND publisher_run_id IS NULL`).bind(publisher,task.job_id).run();
 need(result.success===true,"runtime_lease_storage");
 const current=await db.prepare("SELECT * FROM runtime_credential_leases WHERE job_id=?").bind(task.job_id).first();
 need(current.publisher_run_id===publisher,"runtime_publisher_bound");
 return {context:JSON.parse(current.context_json),cipher_sha256:current.cipher_sha256};
}
export async function publishRuntimeLease(db,task,publisher,value,now){
 const pending=await pendingRuntimeLease(db,task,publisher,now);
 need(canonical(value.context||{})===canonical(pending.context)&&typeof value.ciphertext==="string"&&
  value.ciphertext.length<=349528&&/^[A-Za-z0-9+/]+={0,2}$/.test(value.ciphertext),"runtime_publish_binding");
 const raw=Uint8Array.from(atob(value.ciphertext),c=>c.charCodeAt(0));
 need(raw.length<=262144&&new TextDecoder().decode(raw.slice(0,22))==="age-encryption.org/v1\n","runtime_cipher_format");
 const digest=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",raw)),v=>v.toString(16).padStart(2,"0")).join("");
 const result=await db.prepare(`UPDATE runtime_credential_leases SET ciphertext=?,cipher_sha256=?,published_at=?
  WHERE job_id=? AND publisher_run_id=? AND cipher_sha256 IS NULL AND consumed_at IS NULL AND expires_at>?`)
  .bind(value.ciphertext,digest,now,task.job_id,publisher,now).run();
 need(result.success===true,"runtime_lease_storage");
 const saved=await db.prepare("SELECT * FROM runtime_credential_leases WHERE job_id=?").bind(task.job_id).first();
 need(saved?.cipher_sha256===digest&&saved.ciphertext===value.ciphertext,"runtime_cipher_immutable");
 return digest;
}
export async function readRuntimeLease(db,task,now){
 const saved=await db.prepare("SELECT * FROM runtime_credential_leases WHERE job_id=?").bind(task.job_id).first();
 need(saved&&saved.expires_at>now&&saved.consumed_at===null,"runtime_lease_expired");
 return saved.ciphertext?{context:JSON.parse(saved.context_json),ciphertext:saved.ciphertext,
  cipher_sha256:saved.cipher_sha256}:{pending:true};
}
export async function closeRuntimeLease(db,task,now){
 const result=await db.prepare(`UPDATE runtime_credential_leases SET ciphertext=NULL,
  consumed_at=COALESCE(consumed_at,?) WHERE job_id=?`).bind(now,task.job_id).run();
 need(result.success===true,"runtime_lease_storage");
}
