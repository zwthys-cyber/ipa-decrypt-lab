// Bounded real canary; never a final Telegram cutover or a replay of source tasks.
import {need} from "./runtime-auth.mjs";
const HASH=/^[a-f0-9]{64}$/;
export const CANARY_SCHEMA=
"CREATE TABLE IF NOT EXISTS runtime_canary_windows(source_sha TEXT PRIMARY KEY,owner_id TEXT NOT NULL,nonce TEXT NOT NULL UNIQUE,snapshot_sha256 TEXT NOT NULL,session_sha256 TEXT NOT NULL,paused_at INTEGER NOT NULL,expires_at INTEGER NOT NULL,request_id TEXT NOT NULL UNIQUE,target TEXT NOT NULL,telegram_update_floor INTEGER NOT NULL,rows_sha256 TEXT NOT NULL,legacy_rows INTEGER NOT NULL,held_rows INTEGER NOT NULL,revoked_at INTEGER);"+
"CREATE TABLE IF NOT EXISTS runtime_canary_legacy(source_sha TEXT NOT NULL,owner_id TEXT NOT NULL,request_id TEXT NOT NULL,profile TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL,created_at INTEGER NOT NULL,source_json TEXT NOT NULL,held INTEGER NOT NULL,PRIMARY KEY(source_sha,owner_id,request_id));";
const digest=async text=>Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(text))),v=>v.toString(16).padStart(2,"0")).join("");
export async function installCanary(env,p,now){
 need(env.RUNTIME_MODE==="staging"&&p&&Object.keys(p).sort().join(",")==="expires_at,legacy,nonce,paused_at,request_id,rows_sha256,session_sha256,snapshot_sha256,target,telegram_update_floor","runtime_canary_packet");
 need(/^[a-f0-9]{32}$/.test(p.nonce||"")&&/^[a-f0-9]{32}$/.test(p.request_id||"")&&/^[1-9][0-9]{4,19}$/.test(p.target||"")&&
  HASH.test(p.snapshot_sha256||"")&&p.session_sha256==="8349899c8806e2481edfc6f8f532d6aaa855f32c241b86951a03ea62df799765"&&
  Number.isSafeInteger(p.paused_at)&&p.paused_at<=now&&p.paused_at>=now-120&&
  Number.isSafeInteger(p.expires_at)&&p.expires_at>now+120&&p.expires_at<=p.paused_at+900&&
  Number.isSafeInteger(p.telegram_update_floor)&&p.telegram_update_floor>=0&&
  Array.isArray(p.legacy)&&p.legacy.length<=2000&&HASH.test(p.rows_sha256||""),"runtime_canary_proof");
 need(await digest(JSON.stringify(p.legacy))===p.rows_sha256,"runtime_canary_rows_digest");
 const ownerScope=await digest("telegram-owner:"+env.RUNTIME_OWNER_ID),seen=new Set();let held=0;
 const queries=[];
 for(const row of p.legacy){
  need(row&&Object.keys(row).sort().join(",")==="created_at,held,owner_id,profile,request_id,source_json,state,target"&&
   /^((cn|tf)_)?[a-f0-9]{32}$/.test(row.request_id||"")&&
   ["default","cn","tf"].includes(row.profile)&&row.profile===(row.request_id.startsWith("tf_")?"tf":row.request_id.startsWith("cn_")?"cn":"default")&&
   ["pending","sending","delivered","cancelled","closed"].includes(row.state)&&
   Number.isSafeInteger(row.created_at)&&row.created_at>=0&&row.created_at<=now&&row.held===(["pending","sending"].includes(row.state)?1:0)&&
   typeof row.source_json==="string"&&row.source_json.length<=4096,"runtime_canary_legacy");
  const original=JSON.parse(row.source_json);
  need(HASH.test(original.scope||"")&&original.rid===row.request_id&&original.app===row.target&&original.state===row.state&&original.created===row.created_at&&
   row.owner_id===(original.scope===ownerScope?env.RUNTIME_OWNER_ID:"legacy:"+original.scope),"runtime_canary_legacy_binding");
  const tag=row.owner_id+":"+row.request_id;need(!seen.has(tag),"runtime_canary_duplicate");seen.add(tag);held+=row.held;
  queries.push(env.DB.prepare("INSERT INTO runtime_canary_legacy VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING")
   .bind(env.RUNTIME_SOURCE_SHA,row.owner_id,row.request_id,row.profile,row.target,row.state,row.created_at,row.source_json,row.held));
 }
 queries.push(env.DB.prepare("INSERT INTO runtime_canary_windows VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,NULL) ON CONFLICT DO NOTHING")
  .bind(env.RUNTIME_SOURCE_SHA,env.RUNTIME_OWNER_ID,p.nonce,p.snapshot_sha256,p.session_sha256,p.paused_at,p.expires_at,p.request_id,p.target,p.telegram_update_floor,p.rows_sha256,p.legacy.length,held));
 const result=await env.DB.batch(queries);need(result.every(x=>x.success===true),"runtime_canary_storage");
 const saved=await canaryWindow(env,now);
 need(saved.nonce===p.nonce&&saved.snapshot_sha256===p.snapshot_sha256&&saved.rows_sha256===p.rows_sha256&&
  saved.request_id===p.request_id&&saved.target===p.target&&saved.expires_at===p.expires_at,"runtime_canary_immutable");
 return {ok:true,legacy_rows:p.legacy.length,held_rows:held,expires_at:saved.expires_at};
}
export async function canaryWindow(env,now){
 const row=await env.DB.prepare("SELECT * FROM runtime_canary_windows WHERE source_sha=? AND owner_id=?").bind(env.RUNTIME_SOURCE_SHA,env.RUNTIME_OWNER_ID).first();
 if(!row)return null;
 need(row.revoked_at===null&&row.expires_at>now,"runtime_canary_closed");
 const rows=await env.DB.prepare("SELECT owner_id,request_id,profile,target,state,created_at,source_json,held FROM runtime_canary_legacy WHERE source_sha=? ORDER BY owner_id,request_id").bind(env.RUNTIME_SOURCE_SHA).all();
 const canonical=(rows.results||[]).map(r=>({owner_id:r.owner_id,request_id:r.request_id,profile:r.profile,target:r.target,state:r.state,created_at:r.created_at,source_json:r.source_json,held:r.held}));
 need(canonical.length===row.legacy_rows&&canonical.reduce((n,r)=>n+r.held,0)===row.held_rows&&await digest(JSON.stringify(canonical))===row.rows_sha256,"runtime_canary_import_binding");
 return {...row,canary:true,lease_deadline:row.expires_at};
}
export async function revokeCanary(env,nonce,now){
 need(/^[a-f0-9]{32}$/.test(nonce||""),"runtime_canary_nonce");
 const result=await env.DB.prepare("UPDATE runtime_canary_windows SET revoked_at=COALESCE(revoked_at,?) WHERE source_sha=? AND owner_id=? AND nonce=?")
  .bind(now,env.RUNTIME_SOURCE_SHA,env.RUNTIME_OWNER_ID,nonce).run();
 need(result.success===true&&result.meta?.changes===1,"runtime_canary_revoke");return {ok:true};
}
