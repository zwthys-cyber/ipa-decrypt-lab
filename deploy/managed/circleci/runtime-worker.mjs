import {handle} from "../free-pilot/worker.mjs";
import {handleRuntimeV2} from "./runtime-api.mjs";
export default {fetch(request,env){
 if(new URL(request.url).pathname.startsWith("/v2/runtime/"))return handleRuntimeV2(request,env);
 return handle(request,env);
}};
