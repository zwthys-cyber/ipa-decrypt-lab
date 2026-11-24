// Optional edge ingress for the managed state service. No state or credentials are stored here.
const OPS = new Set(["/v1/status", "/v1/fetch", "/v1/claim", "/v1/finish"]);
const TOKEN = /^[A-Za-z0-9_-]{43,128}$/;
const LIMIT = 16384;
const RESPONSE_LIMIT = 400000;
function result(status, body = {status:"failed"}) {
  return new Response(JSON.stringify(body), {status, headers:{"content-type":"application/json","cache-control":"no-store"}});
}
function validToken(x) { return typeof x === "string" && TOKEN.test(x); }
async function equal(a,b) {
  const enc = new TextEncoder();
  const left = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(a)));
  const right = new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(b)));
  let diff=0;
  for(let i=0;i<left.length;i++) diff |= left[i]^right[i];
  return diff===0;
}
async function bounded(stream, max) {
  if (!stream) throw new Error("missing_body");
  const reader=stream.getReader(), chunks=[];
  let size=0;
  try {
    for(;;) {
      const {done,value}=await reader.read();
      if(done) break;
      size+=value.byteLength;
      if(size>max){await reader.cancel();throw new Error("oversized");}
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  if(!size)throw new Error("empty");
  const body=new Uint8Array(size);
  let offset=0;
  for(const chunk of chunks){body.set(chunk,offset);offset+=chunk.byteLength;}
  return body;
}
function upstreamOrigin(value) {
  if(typeof value!=="string" || !/^https:\/\/[A-Za-z0-9.-]{1,253}(?::443)?\/?$/.test(value))throw new Error("invalid_origin");
  const url=new URL(value);
  if(!url.hostname || url.username || url.password || url.pathname!=="/" || url.search || url.hash)throw new Error("invalid_origin");
  return url.origin;
}
export async function handle(request,env,send=fetch) {
  try {
    const url=new URL(request.url);
    if(request.method!=="POST" || !OPS.has(url.pathname) || url.search)return result(404);
    if(!validToken(env.EDGE_TOKEN) || !validToken(env.ORIGIN_TOKEN) || env.EDGE_TOKEN===env.ORIGIN_TOKEN)return result(503);
    const header=request.headers.get("authorization")||"";
    if(!/^Bearer [A-Za-z0-9_-]{43,128}$/.test(header) || !await equal(header,"Bearer "+env.EDGE_TOKEN))return result(401);
    if(request.headers.get("content-type")!=="application/json")return result(400);
    const length=request.headers.get("content-length");
    if(length!==null && (!/^\d{1,5}$/.test(length)||Number(length)<1||Number(length)>LIMIT))return result(413);
    let body;
    try {
      body=await bounded(request.body,LIMIT);
      const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(body));
      if(!value || typeof value!=="object" || Array.isArray(value))return result(400);
    } catch {return result(400);}
    const origin=upstreamOrigin(env.STATE_ORIGIN);
    if(origin===url.origin)return result(503);
    // Exactly one attempt. Never forward caller headers, follow redirects, retry claims, or log bodies.
    const response=await send(origin+url.pathname,{method:"POST",redirect:"manual",cache:"no-store",
      headers:{"authorization":"Bearer "+env.ORIGIN_TOKEN,"content-type":"application/json","accept":"application/json","cache-control":"no-store"},body});
    if(response.status!==200 || response.headers.get("content-type")!=="application/json")return result(502);
    const bytes=await bounded(response.body,RESPONSE_LIMIT);
    const value=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));
    if(!value || typeof value!=="object" || Array.isArray(value) || value.status==="failed")return result(502);
    return result(200,value);
  } catch {return result(502);}
}
export default {fetch(request,env){return handle(request,env);}};
