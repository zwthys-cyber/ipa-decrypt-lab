"""CI-only guarded maintenance fixture. No live service, credentials or controller execution."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import maintenance_close as maintenance

class MaintenanceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.bundle=self.root/"worker.mjs";self.bundle.write_text("export default {}")
  self.source="a"*40;(self.root/"BUILDINFO").write_text("source_commit="+self.source+"\n")
  self.env=dict(GITHUB_ACTIONS="true",GITHUB_REPOSITORY="zwthys-cyber/ipa-decrypt-lab",
   GITHUB_REF="refs/heads/"+maintenance.BRANCH,GITHUB_EVENT_NAME="workflow_dispatch",GITHUB_RUN_ATTEMPT="1",
   GITHUB_ACTOR_ID="246379322",GITHUB_SHA="b"*40,CF_ACCOUNT_ID="c"*32,CF_API_TOKEN="synthetic")
  self.settings=dict(bindings=[dict(name="DB",type="d1",id="12345678-1234-1234-1234-123456789abc"),
   dict(name="PILOT_ENABLED",type="plain_text",text="0"),dict(name="PILOT_LINK_ENABLED",type="plain_text",text="0"),
   dict(name="RUNTIME_SOURCE_SHA",type="plain_text",text=self.source),dict(name="RUNTIME_MODE",type="plain_text",text="production")])
  self.posts=0
 def api(self,account,token,path,data=None,method=None,**kwargs):
  if path.endswith("/settings"):return self.settings
  self.posts+=1
  metadata=json.loads(data.split(b"\r\n\r\n",1)[1].split(b"\r\n--",1)[0])
  self.settings=dict(bindings=metadata["bindings"])
  return {}
 def test_active_tasks_prevent_any_configuration_write(self):
  with patch.object(maintenance,"api",side_effect=self.api),patch.object(maintenance,"public",return_value=(200,dict(source_sha=self.source,active=True))):
   with self.assertRaisesRegex(ValueError,"maintenance_active_tasks"):maintenance.close(self.bundle,self.source,self.env)
  self.assertEqual(self.posts,0)
 def test_exact_old_bundle_is_closed_without_changing_live_source_or_database(self):
  def public(path,body=None):
   return (503,{}) if path=="telegram" else (200,dict(source_sha=self.source,active=False))
  previous=os.getcwd()
  try:
   os.chdir(self.root)
   with patch.object(maintenance,"api",side_effect=self.api),patch.object(maintenance,"public",side_effect=public),patch("builtins.print"):
    proof=maintenance.close(self.bundle,self.source,self.env)
  finally:os.chdir(previous)
  self.assertTrue(proof["entry_closed"]);self.assertTrue(proof["source_unchanged"])
  values={x["name"]:x for x in self.settings["bindings"]}
  self.assertEqual(values["RUNTIME_SOURCE_SHA"]["text"],self.source)
  self.assertNotEqual(values["RUNTIME_SOURCE_SHA"]["text"],self.env["GITHUB_SHA"])
  self.assertEqual(values["RUNTIME_MODE"]["text"],"staging")
  self.assertEqual(values["RUNTIME_EXPORT_ENABLED"]["text"],"0")
 def test_wrong_context_or_bundle_fails_before_provider_access(self):
  with patch.object(maintenance,"api") as api:
   with self.assertRaisesRegex(ValueError,"maintenance_context"):maintenance.close(self.bundle,self.source,dict(self.env,GITHUB_REF="refs/heads/main"))
   with self.assertRaisesRegex(ValueError,"maintenance_bundle"):maintenance.close(self.bundle,"f"*40,self.env)
   api.assert_not_called()
if __name__=="__main__":unittest.main()
