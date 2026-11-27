"""CI-only orchestration guards; no Cloudflare, Telegram, Apple or legacy service operations."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import offline_cutover as cut

class CutoverTests(unittest.TestCase):
 def test_mode_retains_database_and_keeps_billing_and_legacy_flags_off(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
  bundle=Path(temp.name)/"worker.mjs";bundle.write_text("export default {}")
  settings=dict(bindings=[dict(type="d1",name="DB",id="12345678-1234-1234-1234-123456789abc"),
    dict(type="plain_text",name="PILOT_ENABLED",text="0"),dict(type="plain_text",name="PILOT_LINK_ENABLED",text="0")])
  seen=[]
  def api(account,token,path,data=None,method=None,**kwargs):
   nonlocal settings
   if path.endswith("/settings"):return settings
   seen.append(json.loads(data.split(b"\r\n\r\n",1)[1].split(b"\r\n--",1)[0]))
   settings=dict(bindings=seen[-1]["bindings"])
   return {}
  env=dict(CF_ACCOUNT_ID="a"*32,CF_API_TOKEN="synthetic",GITHUB_SHA="b"*40)
  with patch.object(cut,"api",side_effect=api):
   cut.mode(bundle,env,True);cut.mode(bundle,env,False)
  for metadata in seen:
   values={v["name"]:v for v in metadata["bindings"]}
   self.assertEqual(values["DB"],dict(type="d1",name="DB",id="12345678-1234-1234-1234-123456789abc"))
   self.assertEqual(values["RUNTIME_BILLING_ENABLED"]["text"],"0")
   self.assertEqual(values["PILOT_ENABLED"]["text"],"0")
  self.assertEqual(next(v for v in seen[-1]["bindings"] if v["name"]=="RUNTIME_MODE")["text"],"staging")

 def test_cron_preserves_existing_schedules_and_readback_must_match(self):
  env=dict(CF_ACCOUNT_ID="a"*32,CF_API_TOKEN="synthetic")
  existing=[dict(cron="0 * * * *")]
  def api(account,token,path,data=None,method=None,**kwargs):
   nonlocal existing
   if data is not None:existing=data
   return dict(schedules=existing)
  with patch.object(cut,"api",side_effect=api):cut.schedules(env)
  self.assertEqual({v["cron"] for v in existing},{"0 * * * *","* * * * *"})
  with patch.object(cut,"api",return_value=dict(schedules=[dict(cron=str(i)) for i in range(3)])):
   with self.assertRaisesRegex(ValueError,"offline_cron_limit"):cut.schedules(env)

 def test_existing_minute_schedule_is_read_without_restarting_propagation(self):
  env=dict(CF_ACCOUNT_ID="a"*32,CF_API_TOKEN="synthetic")
  with patch.object(cut,"api",return_value=dict(schedules=[dict(cron="* * * * *")])) as api:
   cut.schedules(env)
  self.assertEqual(api.call_count,1)
  self.assertNotIn("method",api.call_args.kwargs)

 def test_invalid_owner_or_missing_hmac_never_deploys_or_changes_mode(self):
  with patch.dict(os.environ,{},clear=True),patch.object(cut,"deploy") as deploy,patch.object(cut,"mode") as mode:
   with self.assertRaisesRegex(ValueError,"offline_cutover_context"):cut.run("unused")
   deploy.assert_not_called();mode.assert_not_called()

 def test_bot_scope_rejects_non_configuration_method_before_transport(self):
  with patch.object(cut.urllib.request,"build_opener") as transport:
   with self.assertRaisesRegex(ValueError,"offline_bot_method"):cut.bot("sendMessage","123456789:"+"X"*36,{})
   transport.assert_not_called()

if __name__=="__main__":unittest.main()
