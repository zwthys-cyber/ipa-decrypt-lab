import {writeFileSync} from "node:fs";
import {fetchKeys,verifyCircleJWT} from "./oidc.mjs";
const token=process.env.CIRCLE_OIDC_TOKEN_V3||"";
let result={schema:"circleci-oidc-v3-probe-v1",available:!!token,verified:false};
try{
  if(token){
    const identity=await verifyCircleJWT(token,{run:process.env.PROBE_PIPELINE,
      job:process.env.CIRCLE_WORKFLOW_JOB_ID},await fetchKeys());
    result={...result,verified:true,identity};
  }
  writeFileSync("dispatch-probe-out/oidc-receipt.json",JSON.stringify(result)+"\n",{mode:0o600});
  console.log(JSON.stringify(result));
}catch(error){
  const reason=typeof error?.message==="string"&&/^(jwt_[a-z_]+|jwks_[a-z_]+|expected_identity)$/.test(error.message)
    ?error.message:"circleci_oidc_probe_failed";
  console.error(reason);process.exitCode=1;
}
