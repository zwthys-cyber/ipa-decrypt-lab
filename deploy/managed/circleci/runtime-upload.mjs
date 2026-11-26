// Durable private upload state; the existing native uploader keeps its no-recreate policy.
const JOB=/^pilot_[a-f0-9]{32}$/,HASH=/^[a-f0-9]{64}$/,SHA=/^[a-f0-9]{40}$/;
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
function require(ok,code){if(!ok)throw Error(code);}
export const UPLOAD_SCHEMA=`CREATE TABLE IF NOT EXISTS runtime_uploads(
  job_id TEXT PRIMARY KEY,owner_id TEXT NOT NULL,worker_job_id TEXT NOT NULL,source_sha TEXT NOT NULL,
  binding_json TEXT NOT NULL,stage TEXT NOT NULL CHECK(stage IN ('start_intent','uploading','uploaded','registration_intent','registered')),
  state_json TEXT NOT NULL,revision INTEGER NOT NULL,updated_at INTEGER NOT NULL
);`;
function context(task){
  require(task&&JOB.test(task.job_id||"")&&/^[1-9][0-9]{0,15}$/.test(task.owner_id||"")&&
    UUID.test(task.worker_job_id||"")&&SHA.test(task.source_sha||"")&&
    ["running","uploading","link_ready"].includes(task.state)&&(task.kind==="export"||(task.kind==="fixture"&&task.drive_fixture===1&&task.fixture_authorized===1))&&
    HASH.test(task.plaintext_sha256||"")&&Number.isSafeInteger(task.plaintext_bytes)&&
    task.plaintext_bytes>0&&task.plaintext_bytes<=2000000000&&
    /^[^\s@]{1,128}@[^\s@]{1,128}$/.test(task.recipient_email||""),"upload_context");
}
function record(value,task){
  require(value&&Object.keys(value).sort().join(",")==="bytes,filename,sha256"&&
    value.sha256===task.plaintext_sha256&&value.bytes===task.plaintext_bytes&&
    typeof value.filename==="string"&&value.filename===task.filename&&value.filename.length<=160&&
    /^[\p{L}\p{N} ._()\-]+\.ipa$/iu.test(value.filename)&&!value.filename.startsWith("."),"upload_plaintext_binding");
  return {filename:value.filename,bytes:value.bytes,sha256:value.sha256};
}
function session(value){
  require(typeof value==="string"&&value.length<=4096,"upload_session");
  const url=new URL(value);
  require(url.protocol==="https:"&&url.hostname==="www.googleapis.com"&&!url.username&&!url.password&&
    !url.port&&!url.hash&&url.pathname==="/upload/drive/v3/files"&&url.searchParams.get("uploadType")==="resumable"&&
    /^[A-Za-z0-9._~+\/=-]{10,2048}$/.test(url.searchParams.get("upload_id")||"")&&
    [...url.searchParams.keys()].every(k=>["uploadType","upload_id","fields","supportsAllDrives","supportsTeamDrives","prettyPrint","alt","upload_protocol"].includes(k))&&
    (!url.searchParams.has("fields")||url.searchParams.get("fields")==="id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey")&&
    ["supportsAllDrives","supportsTeamDrives","prettyPrint"].every(k=>!url.searchParams.has(k)||url.searchParams.get(k)==="false")&&
    (!url.searchParams.has("alt")||url.searchParams.get("alt")==="json")&&
    (!url.searchParams.has("upload_protocol")||url.searchParams.get("upload_protocol")==="resumable")&&
    [...url.searchParams.keys()].length===new Set(url.searchParams.keys()).size,"upload_session");
}
function shape(value,task){
  require(value&&value.job_id===task.job_id&&value.owner===task.recipient_email.toLowerCase(),"upload_owner_binding");
  const content=record(value.record,task);
  const stage=value.stage;
  const extra=stage==="uploading"?["session"]:["uploaded","registration_intent","registered"].includes(stage)?["file_id"]:[];
  if(["registration_intent","registered"].includes(stage))extra.push("registration_origin");
  require(["start_intent","uploading","uploaded","registration_intent","registered"].includes(stage)&&
    Object.keys(value).sort().join(",")===["job_id","record","owner","stage",...extra].sort().join(","),"upload_state_fields");
  const result={job_id:task.job_id,record:content,owner:value.owner,stage};
  if(stage==="uploading"){session(value.session);result.session=value.session;}
  if(value.file_id!==undefined){
    require(/^[A-Za-z0-9_-]{10,160}$/.test(value.file_id),"upload_file_id");result.file_id=value.file_id;
  }
  if(value.registration_origin!==undefined){
    require(value.registration_origin===task.control_origin,"upload_registration_origin");
    result.registration_origin=value.registration_origin;
  }
  return result;
}
async function row(db,task){
  return db.prepare("SELECT * FROM runtime_uploads WHERE job_id=?").bind(task.job_id).first();
}
function owned(saved,task){
  require(saved.owner_id===task.owner_id&&saved.worker_job_id===task.worker_job_id&&saved.source_sha===task.source_sha,
    "upload_journal_owner");
}
export async function readUploadJournal(db,task){
  context(task);const saved=await row(db,task);if(!saved)return null;
  owned(saved,task);return JSON.parse(saved.state_json);
}
export async function writeUploadJournal(db,task,value,now){
  context(task);require(Number.isSafeInteger(now)&&now>=0,"upload_time");
  const state=shape(value,task),encoded=JSON.stringify(state);
  const binding=JSON.stringify({job_id:task.job_id,record:state.record,owner:state.owner});
  let saved=await row(db,task);
  if(!saved){
    require(state.stage==="start_intent","upload_intent_required");
    const result=await db.prepare(`INSERT INTO runtime_uploads
      (job_id,owner_id,worker_job_id,source_sha,binding_json,stage,state_json,revision,updated_at)
      VALUES(?,?,?,?,?,'start_intent',?,1,?) ON CONFLICT(job_id) DO NOTHING`)
      .bind(task.job_id,task.owner_id,task.worker_job_id,task.source_sha,binding,encoded,now).run();
    require(result.success===true,"upload_journal_storage");
    saved=await row(db,task);owned(saved,task);
    require(saved.state_json===encoded,"upload_journal_conflict");return {ok:true,revision:saved.revision};
  }
  owned(saved,task);require(saved.binding_json===binding,"upload_journal_binding");
  if(saved.state_json===encoded)return {ok:true,revision:saved.revision};
  const transitions={start_intent:"uploading",uploading:"uploaded",uploaded:"registration_intent"};
  require(transitions[saved.stage]===state.stage,"upload_state_transition");
  const previous=JSON.parse(saved.state_json);
  if(previous.file_id)require(previous.file_id===state.file_id,"upload_file_immutable");
  const result=await db.prepare(`UPDATE runtime_uploads SET stage=?,state_json=?,revision=revision+1,updated_at=?
    WHERE job_id=? AND revision=? AND state_json=?`).bind(state.stage,encoded,now,task.job_id,saved.revision,saved.state_json).run();
  require(result.success===true&&result.meta?.changes===1,"upload_journal_concurrent");
  return {ok:true,revision:saved.revision+1};
}
export async function confirmUploadRegistration(db,task,fileId,now){
  // Only the server calls this after independently checking Drive SHA/size/name and owner-only ACL.
  context(task);const saved=await row(db,task);require(saved,"upload_registration_missing");owned(saved,task);
  const state=JSON.parse(saved.state_json);
  require(["registration_intent","registered"].includes(state.stage)&&state.file_id===fileId,"upload_registration_binding");
  if(state.stage==="registered")return {ok:true};
  state.stage="registered";
  const result=await db.prepare(`UPDATE runtime_uploads SET stage='registered',state_json=?,revision=revision+1,updated_at=?
    WHERE job_id=? AND revision=? AND stage='registration_intent'`).bind(JSON.stringify(state),now,task.job_id,saved.revision).run();
  require(result.success===true&&result.meta?.changes===1,"upload_journal_concurrent");return {ok:true};
}
