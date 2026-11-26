// Actual GitHub OIDC proof. No JWT or request token is printed or retained.
import {writeFileSync} from "node:fs";
import {GITHUB_TRUST as T,verifyGithubJWT,fetchGithubKeys} from "./github-oidc.mjs";
try{
  if(process.env.GITHUB_ACTIONS!=="true"||process.env.GITHUB_REPOSITORY!==T.repository||
    process.env.GITHUB_REF!==T.ref)throw Error("publisher_probe_context");
  const url=new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);
  if(url.protocol!=="https:"||!url.hostname.endsWith(".actions.githubusercontent.com")||
    url.username||url.password||url.port||url.hash)throw Error("publisher_oidc_endpoint");
  url.searchParams.set("audience",T.audience);
  const response=await fetch(url,{redirect:"error",signal:AbortSignal.timeout(15000),
    headers:{authorization:"Bearer "+process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}});
  if(response.status!==200)throw Error("publisher_oidc_request");
  const raw=await response.text();if(raw.length>32768)throw Error("publisher_oidc_limit");
  const token=JSON.parse(raw).value;
  const identity=await verifyGithubJWT(token,{source:process.env.GITHUB_SHA,run:process.env.GITHUB_RUN_ID,role:"probe"},
    await fetchGithubKeys());
  writeFileSync("publisher-identity-proof.json",JSON.stringify(identity)+"\n",{mode:0o600});
  console.log(JSON.stringify(identity));
}catch{
  console.error("publisher_identity_probe_failed");process.exitCode=1;
}
