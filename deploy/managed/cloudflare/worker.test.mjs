import test from "node:test";
import assert from "node:assert/strict";
import {handle} from "./worker.mjs";

const env={EDGE_TOKEN:"a".repeat(48),ORIGIN_TOKEN:"b".repeat(48),STATE_ORIGIN:"https://origin.example.invalid"};
function request(path="/v1/status", options={}) {
  return new Request("https://edge.example.invalid"+path,{method:"POST",body:"{}",headers:{"content-type":"application/json",authorization:"Bearer "+env.EDGE_TOKEN},...options});
}
const success=()=>new Response('{"ready":true}',{headers:{"content-type":"application/json"}});
test("closed routes, auth and length checks reject before upstream",async()=>{
  const denied=()=>{throw new Error("unexpected upstream");};
  assert.equal((await handle(request("/v1/install"),env,denied)).status,404);
  assert.equal((await handle(request("/v1/status?x=1"),env,denied)).status,404);
  assert.equal((await handle(request("/v1/status",{headers:{"content-type":"application/json"}}),env,denied)).status,401);
  assert.equal((await handle(request("/v1/status",{body:JSON.stringify({x:"x".repeat(17000)})}),env,denied)).status,400);
});
test("only dedicated origin authorization is forwarded",async()=>{
  let calls=0;
  const res=await handle(request("/v1/fetch"),env,async(url,init)=>{
    calls++;
    assert.equal(url,"https://origin.example.invalid/v1/fetch");
    assert.equal(init.headers.authorization,"Bearer "+env.ORIGIN_TOKEN);
    assert.equal(init.redirect,"manual");
    assert.equal(init.cache,"no-store");
    return success();
  });
  assert.equal(calls,1);assert.equal(res.status,200);
  assert.equal(res.headers.get("cache-control"),"no-store");
  assert.deepEqual(await res.json(),{ready:true});
});
test("ambiguous failures and redirects never retry",async()=>{
  let calls=0;
  const send=async()=>{calls++;return new Response("",{status:307,headers:{location:"https://elsewhere.invalid"}});};
  assert.equal((await handle(request("/v1/claim"),env,send)).status,502);
  assert.equal(calls,1);
  assert.equal((await handle(request("/v1/finish"),env,async()=>{calls++;throw Error("network");})).status,502);
  assert.equal(calls,2);
});
test("invalid origin and shared token fail closed",async()=>{
  const denied=()=>{throw Error("unexpected upstream");};
  assert.equal((await handle(request(),{...env,STATE_ORIGIN:"http://origin.example.invalid"},denied)).status,502);
  assert.equal((await handle(request(),{...env,ORIGIN_TOKEN:env.EDGE_TOKEN},denied)).status,503);
});
