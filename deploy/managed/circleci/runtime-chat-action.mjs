// A brief owner-private reply hint; it never represents background task progress.
export async function showTyping(env,send=fetch){
 const owner=env.RUNTIME_OWNER_ID,token=env.TELEGRAM_BOT_TOKEN||"";
 if(env.RUNTIME_TELEGRAM_ENABLED!=="1"||typeof owner!=="string"||!/^[1-9][0-9]{0,19}$/.test(owner)||!Number.isSafeInteger(Number(owner))||
  !/^[0-9]{5,20}:[A-Za-z0-9_-]{30,90}$/.test(token))return false;
 try{
  const response=await send("https://api.telegram.org/bot"+token+"/sendChatAction",{
   method:"POST",redirect:"manual",signal:AbortSignal.timeout(1000),
   headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:Number(owner),action:"typing"})
  });
  return response.ok;
 }catch{return false;}
}
