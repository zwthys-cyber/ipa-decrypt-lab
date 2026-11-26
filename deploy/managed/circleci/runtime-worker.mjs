import {handle} from "../free-pilot/worker.mjs";
import {handleRuntimeV2} from "./runtime-api.mjs";
import {handleManagedTelegram} from "./runtime-telegram.mjs";
export default {fetch(request,env){
 const path=new URL(request.url).pathname;
 if(path.startsWith("/v2/runtime/"))return handleRuntimeV2(request,env);
 if(path==="/telegram"&&env.RUNTIME_MODE==="production"){
  const invoke=async(endpoint,value)=>{
   if(!["admit-export","status","owner-get","owner-cancel"].includes(endpoint))throw Error("runtime_entry_endpoint");
   const result=await handleRuntimeV2(new Request(env.RUNTIME_CONTROL_ORIGIN+"/v2/runtime/"+endpoint,{
    method:"POST",headers:{"content-type":"application/json","x-ipazake-source-sha":env.RUNTIME_SOURCE_SHA,
     "x-ipazake-control-token":env.CIRCLECI_CONTROL_TOKEN},body:JSON.stringify({...value,_source:env.RUNTIME_SOURCE_SHA})}),env);
   const reply=await result.json();if(!reply.ok)throw Error(reply.code||"runtime_entry_unavailable");return reply;
  };
  return handleManagedTelegram(request,env,invoke);
 }
 return handle(request,env);
}};
