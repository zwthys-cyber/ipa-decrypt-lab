// Standard server-side Google OAuth. Configuration belongs to the owner's runtime.
// Access tokens are request-local; no credentials or provider responses are logged.
export const SCOPE="https://www.googleapis.com/auth/drive.file";
const ACCESS=/^[A-Za-z0-9._~+\/=-]{20,2048}$/;
const CLIENT=/^[A-Za-z0-9_-]{10,240}\.apps\.googleusercontent\.com$/;
const OPAQUE=/^[\x21-\x7e]{12,2048}$/;
function valid(v,pattern){return typeof v==="string"&&pattern.test(v);}
export function authMode(env){
  const values=[env.PILOT_DRIVE_CLIENT_ID,env.PILOT_DRIVE_CLIENT_SECRET,env.PILOT_DRIVE_REFRESH_TOKEN];
  if(values.some(v=>v!==undefined&&v!=="")){
    return valid(values[0],CLIENT)&&valid(values[1],OPAQUE)&&valid(values[2],OPAQUE)?"refresh":null;
  }
  return valid(env.PILOT_DRIVE_ACCESS_TOKEN,ACCESS)?"manual":null;
}
async function jsonBounded(response){
  if(response.status!==200||!response.body)throw Error("drive_authorization_unavailable");
  const reader=response.body.getReader();
  const chunks=[];let size=0;
  try{
    for(;;){
      const {done,value}=await reader.read();if(done)break;
      size+=value.byteLength;
      if(size>16384){await reader.cancel();throw Error("drive_authorization_unavailable");}
      chunks.push(value);
    }
  }finally{reader.releaseLock();}
  const data=new Uint8Array(size);let at=0;
  for(const chunk of chunks){data.set(chunk,at);at+=chunk.byteLength;}
  return JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(data));
}
export async function accessForRequest(env,send=fetch){
  try{
    const mode=authMode(env);
    if(mode==="manual")return env.PILOT_DRIVE_ACCESS_TOKEN;
    if(mode!=="refresh")throw Error("drive_authorization_unavailable");
    const response=await send("https://oauth2.googleapis.com/token",{
      method:"POST",redirect:"error",
      headers:{"Content-Type":"application/x-www-form-urlencoded",Accept:"application/json"},
      body:new URLSearchParams({
        grant_type:"refresh_token",
        client_id:env.PILOT_DRIVE_CLIENT_ID,
        client_secret:env.PILOT_DRIVE_CLIENT_SECRET,
        refresh_token:env.PILOT_DRIVE_REFRESH_TOKEN
      }).toString()
    });
    const token=await jsonBounded(response);
    if(!token||!valid(token.access_token,ACCESS)||
       typeof token.token_type!=="string"||token.token_type.toLowerCase()!=="bearer"||
       !Number.isSafeInteger(token.expires_in)||token.expires_in<120||token.expires_in>86400||
       typeof token.scope!=="string"||token.scope.trim()!==SCOPE||
       token.refresh_token!==undefined)
      throw Error("drive_authorization_unavailable");
    return token.access_token;
  }catch{throw Error("drive_authorization_unavailable");}
}
