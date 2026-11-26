// Synthetic-only opaque age transport. No Apple profile is accepted by these routes.
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
function require(ok,code){if(!ok)throw Error(code);}
export const LEASE_SCHEMA=`CREATE TABLE IF NOT EXISTS circleci_credential_leases (
  job_id TEXT PRIMARY KEY REFERENCES circleci_claims(job_id),
  context_json TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  ciphertext TEXT,
  cipher_sha256 TEXT,
  published_at INTEGER,
  consumed_at INTEGER
);`;
async function row(db,job,now){
  await db.prepare("UPDATE circleci_credential_leases SET ciphertext=NULL,consumed_at=COALESCE(consumed_at,?) WHERE job_id=? AND expires_at<=?")
    .bind(now,job,now).run();
  return db.prepare("SELECT * FROM circleci_credential_leases WHERE job_id=?").bind(job).first();}
function bound(task,now){
  require(task?.kind==="synthetic_noop"&&task.dispatch_state==="submitted"&&
    UUID.test(task.run_id||"")&&UUID.test(task.worker_job_id||"")&&task.finished_at===null,"lease_task_closed");
}
export async function requestLease(db,task,value,now){
  bound(task,now);
  require(/^age1[0-9a-z]{58}$/.test(value.recipient||"")&&/^[a-f0-9]{32}$/.test(value.nonce||"")&&
    Number.isSafeInteger(value.expires_at)&&now<value.expires_at&&value.expires_at<=now+300,"lease_request_invalid");
  const context={schema:"circleci-credential-request-v1",job_id:task.job_id,run_id:task.run_id,
    worker_job_id:task.worker_job_id,source_sha:task.source_sha,recipient:value.recipient,
    nonce:value.nonce,expires_at:value.expires_at,profile:"synthetic"};
  const encoded=JSON.stringify(context);
  const result=await db.prepare(
    "INSERT INTO circleci_credential_leases(job_id,context_json,expires_at) VALUES(?,?,?) ON CONFLICT(job_id) DO NOTHING"
  ).bind(task.job_id,encoded,context.expires_at).run();
  require(result.success===true,"lease_storage");
  const saved=await row(db,task.job_id,now);
  require(saved?.context_json===encoded&&!saved.consumed_at,"lease_request_immutable");
  return {ok:true,context};
}
export async function pendingLease(db,task,now){
  bound(task,now);
  const saved=await row(db,task.job_id,now);
  if(!saved)return {ok:true,pending:true};
  require(saved.expires_at>now&&!saved.consumed_at,"lease_expired");
  return {ok:true,context:JSON.parse(saved.context_json),published:!!saved.cipher_sha256};
}
export async function publishLease(db,task,value,now){
  bound(task,now);
  const saved=await row(db,task.job_id,now);
  require(saved&&saved.expires_at>now&&!saved.consumed_at,"lease_expired");
  const expected=JSON.parse(saved.context_json),given=value.context;
  require(given&&Object.keys(given).sort().join(",")===Object.keys(expected).sort().join(",")&&
    Object.keys(expected).every(k=>expected[k]===given[k]),"lease_publish_binding");
  require(typeof value.ciphertext==="string"&&value.ciphertext.length<=349528&&
    /^[A-Za-z0-9+/]+={0,2}$/.test(value.ciphertext),"lease_cipher_invalid");
  const raw=Uint8Array.from(atob(value.ciphertext),c=>c.charCodeAt(0));
  require(raw.length<=262144&&new TextDecoder().decode(raw.slice(0,22))==="age-encryption.org/v1\n","lease_cipher_format");
  const sha=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",raw)),v=>v.toString(16).padStart(2,"0")).join("");
  const result=await db.prepare(
    "UPDATE circleci_credential_leases SET ciphertext=?,cipher_sha256=?,published_at=? WHERE job_id=? AND cipher_sha256 IS NULL AND consumed_at IS NULL AND expires_at>?"
  ).bind(value.ciphertext,sha,now,task.job_id,now).run();
  require(result.success===true,"lease_storage");
  const current=await row(db,task.job_id,now);
  require(current?.cipher_sha256===sha&&current.ciphertext===value.ciphertext,"lease_cipher_immutable");
  return {ok:true,cipher_sha256:sha};
}
export async function readLease(db,task,now){
  bound(task,now);
  const saved=await row(db,task.job_id,now);
  require(saved&&saved.expires_at>now&&!saved.consumed_at,"lease_expired");
  return saved.ciphertext?{ok:true,context:JSON.parse(saved.context_json),
    ciphertext:saved.ciphertext,cipher_sha256:saved.cipher_sha256}:{ok:true,pending:true};
}
export async function closeLease(db,job,now){
  const result=await db.prepare(
    "UPDATE circleci_credential_leases SET ciphertext=NULL,consumed_at=COALESCE(consumed_at,?) WHERE job_id=?"
  ).bind(now,job).run();
  require(result.success===true,"lease_storage");
}
