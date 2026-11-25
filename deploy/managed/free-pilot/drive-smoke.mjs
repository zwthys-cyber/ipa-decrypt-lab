// Explicit, bounded deployment smoke fixture; not a general-purpose upload route.
// Never logs or returns credentials, file IDs, session URLs, account names or raw provider data.
import {accessForRequest,authMode,googleFetch} from "./drive-auth.mjs";
export const NAME="ipazake-free-pilot-smoke-20261124.txt";
export const SIZE=1024;
const FIXTURE=new TextEncoder().encode(("ipazake free pilot transfer verification; synthetic data only.\n"+"-".repeat(SIZE)).slice(0,SIZE));
const MARKER="free-pilot-smoke-v1";
const ROOT="https://www.googleapis.com";
const FIELDS="id,name,size,sha256Checksum,trashed,ownedByMe,mimeType,resourceKey,appProperties";
const ID=/^[A-Za-z0-9_-]{10,160}$/;
function need(ok,reason){if(!ok)throw Error(reason);}
async function read(response,max){
  need(response.body,"response_missing");
  const chunks=[];let n=0;const reader=response.body.getReader();
  try{
    for(;;){const {done,value}=await reader.read();if(done)break;n+=value.byteLength;
      if(n>max){await reader.cancel();throw Error("response_too_large")}chunks.push(value)}
  }finally{reader.releaseLock()}
  const data=new Uint8Array(n);let at=0;for(const c of chunks){data.set(c,at);at+=c.byteLength}return data;
}
async function json(response){
  need(response.status===200||response.status===201,"google_status");
  const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(await read(response,32768)));
  need(value&&typeof value==="object"&&!Array.isArray(value),"google_response");return value;
}
async function sha(bytes){
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),n=>n.toString(16).padStart(2,"0")).join("");
}
export function quotaStatus(v,email){
  if(typeof email!=="string"||typeof v?.user?.emailAddress!=="string"||
    v.user.emailAddress.toLowerCase()!==email.toLowerCase())return "account_mismatch";
  const q=v.storageQuota;
  if(!q||typeof q.limit!=="string"||typeof q.usage!=="string"||
    !/^\d{1,16}$/.test(q.limit)||!/^\d{1,16}$/.test(q.usage))return "quota_unavailable";
  const limit=Number(q.limit),used=Number(q.usage);
  if(!Number.isSafeInteger(limit)||!Number.isSafeInteger(used)||limit<=0||used>limit)return "quota_unavailable";
  if(limit>15*1024**3)return "quota_not_free_compatible";
  if(limit-used<SIZE+1000000000)return "quota_insufficient";
  return "ok";
}
function validSession(value){
  const url=new URL(value);
  need(url.origin===ROOT&&!url.username&&!url.password&&!url.hash&&url.pathname==="/upload/drive/v3/files"&&url.search.length<=4096&&!!url.searchParams.get("upload_id"),"session");
  return url.href;
}
export async function smokeTransfer(env,send=googleFetch,{allowCreate=true}={}){
  let stage="configuration",createStarted=false;
  try{
    need(env.PILOT_ENABLED==="0"&&env.PILOT_LINK_ENABLED==="0"&&authMode(env)==="refresh"&&typeof env.PILOT_DRIVE_RECIPIENT_EMAIL==="string","configuration");
    stage="oauth";const token=await accessForRequest(env,send);
    const email=env.PILOT_DRIVE_RECIPIENT_EMAIL;
    const request=(url,init={})=>send(url,{...init,redirect:"manual",signal:AbortSignal.timeout(15000),
      headers:{Authorization:"Bearer "+token,Accept:"application/json",...(init.headers||{})}});
    stage="quota_request";
    const about=await request(ROOT+"/drive/v3/about?fields=user%28emailAddress%29%2CstorageQuota%28limit%2Cusage%29",{method:"GET"});
    if(about.status!==200){
      stage=about.status===403?"quota_api_forbidden":about.status===401?"quota_api_unauthorized":
        about.status===429?"quota_api_limited":"quota_api_unavailable";
      if(about.body)await about.body.cancel();
      throw Error("quota_api_unavailable");
    }
    stage="quota_response";
    const quota=quotaStatus(await json(about),email);
    if(quota!=="ok"){stage=quota;throw Error("quota_validation_failed");}
    const digest=await sha(FIXTURE);
    stage="existing_fixture";
    const search=new URLSearchParams({q:"trashed = false and name = '"+NAME+"' and appProperties has { key='pilot_fixture' and value='"+MARKER+"' }",fields:"nextPageToken,files(id)",pageSize:"10"});
    const prior=await json(await request(ROOT+"/drive/v3/files?"+search.toString()));
    need(!prior.nextPageToken&&Array.isArray(prior.files)&&prior.files.length<=1,"fixture_ambiguous");
    let fileId=prior.files[0]?.id;
    if(prior.files.length===0){
      stage="fixture_missing";
      need(allowCreate===true,"fixture_missing");
      stage="generate_id";
      const ids=await json(await request(ROOT+"/drive/v3/files/generateIds?count=1&space=drive&type=files"));
      need(Array.isArray(ids.ids)&&ids.ids.length===1&&typeof ids.ids[0]==="string"&&ID.test(ids.ids[0]),"id");fileId=ids.ids[0];
      stage="upload_start";
      // A pre-generated ID and exact marker avoid duplicate files on a later explicit inspection.
      const start=await request(ROOT+"/upload/drive/v3/files?uploadType=resumable&fields="+FIELDS,{
        method:"POST",headers:{"Content-Type":"application/json","X-Upload-Content-Type":"application/octet-stream","X-Upload-Content-Length":String(SIZE)},
        body:JSON.stringify({id:fileId,name:NAME,mimeType:"application/octet-stream",appProperties:{pilot_fixture:MARKER}})
      });
      need(start.status===200,"upload_start");const url=validSession(start.headers.get("Location")||"");
      if(start.body)await start.body.cancel();
      stage="upload";createStarted=true;
      const uploaded=await json(await request(url,{method:"PUT",headers:{"Content-Type":"application/octet-stream","Content-Range":"bytes 0-"+(SIZE-1)+"/"+SIZE},body:FIXTURE}));
      need(uploaded.id===fileId,"upload_unconfirmed");
    }
    need(typeof fileId==="string"&&ID.test(fileId),"id");
    stage="metadata";
    const details=await request(ROOT+"/drive/v3/files/"+fileId+"?fields="+FIELDS);
    if(details.status===404){
      stage="metadata_missing";
      if(details.body)await details.body.cancel();
      throw Error("metadata_missing");
    }
    const file=await json(details);
    const invalid=[
      ["metadata_identity",file.id!==fileId||file.name!==NAME||file.appProperties?.pilot_fixture!==MARKER],
      ["metadata_owner",file.ownedByMe!==true||file.trashed!==false],
      ["metadata_size",file.size!==String(SIZE)],
      ["metadata_digest_missing",!file.sha256Checksum],
      ["metadata_digest_mismatch",file.sha256Checksum!==digest],
      // Drive may classify this fixed text fixture from its content and .txt name.
      ["metadata_mime",!["application/octet-stream","text/plain"].includes(file.mimeType)],
      ["metadata_resource_key",Boolean(file.resourceKey)],
    ].find(([,failed])=>failed);
    if(invalid){stage=invalid[0];throw Error(stage);}
    stage="acl";
    const acl=await json(await request(ROOT+"/drive/v3/files/"+fileId+"/permissions?pageSize=100&fields=nextPageToken,permissions(type,role,emailAddress,deleted)"));
    need(!acl.nextPageToken&&Array.isArray(acl.permissions)&&acl.permissions.length===1,"acl");
    const p=acl.permissions[0];
    need(p.type==="user"&&p.role==="owner"&&!p.deleted&&typeof p.emailAddress==="string"&&p.emailAddress.toLowerCase()===email.toLowerCase(),"acl");
    stage="download";
    const download=await request(ROOT+"/drive/v3/files/"+fileId+"?alt=media");
    need(download.status===200,"download_status");
    const bytes=await read(download,SIZE);
    need(bytes.byteLength===SIZE&&await sha(bytes)===digest,"download_hash");
    return {ok:true,bytes:SIZE,sha256:digest,owner_only:true,created:createStarted};
  }catch{
    // A failed create/download outcome is never automatically repeated.
    return {ok:false,stage,upload_may_exist:createStarted};
  }
}
