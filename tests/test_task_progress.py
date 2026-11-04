import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from task_progress import ProgressCard, parse_stage, WorkerProgress
from telegram_api import APIError

RID="a"*32
class ProgressTests(unittest.TestCase):
    def test_feed_is_bound_to_request_and_run(self):
        check={"name":"delivery-progress-"+RID,"external_id":RID+":123",
            "app":{"slug":"github-actions"},"output":{"summary":json.dumps({
                "schema":"ipa-stage-v1","request_id":RID,"run_id":"123","stage":"decrypting"})}}
        self.assertEqual(parse_stage(check,RID,123),"decrypting")
        for key,value in (("external_id",RID+":999"),("name","other"),
                          ("app",{"slug":"other-app"}),("app",None)):
            bad=copy.deepcopy(check);bad[key]=value
            self.assertIsNone(parse_stage(bad,RID,123))
        bad=copy.deepcopy(check);bad["output"]["summary"]="not json"
        self.assertIsNone(parse_stage(bad,RID,123))
        bad=copy.deepcopy(check)
        bad["output"]["summary"]=json.dumps({"schema":"ipa-stage-v1","request_id":RID,
                                             "run_id":"123","stage":"100-percent"})
        self.assertIsNone(parse_stage(bad,RID,123))

    def test_one_message_throttled_edits_and_honest_completion(self):
        bot=Mock();bot.message.return_value={"message_id":7}
        with patch("task_progress.time.monotonic",return_value=1) as clock:
            card=ProgressCard(bot,123,RID)
            card.update("queued")
            card.update("queued")
            bot.edit.assert_not_called()
            clock.return_value=17
            card.update("queued")
            card.update("decrypting")
            self.assertNotIn("%",bot.edit.call_args.args[2])
            card.update("done")
        bot.message.assert_called_once()
        self.assertEqual(bot.edit.call_args.args[:2],(123,7))
        self.assertIn("100%",bot.edit.call_args.args[2])

    def test_edit_failure_does_not_post_a_duplicate_card(self):
        bot=Mock();bot.message.return_value={"message_id":7}
        card=ProgressCard(bot,123,RID)
        card.update("queued")
        bot.edit.side_effect=APIError("telegram_transport_unknown")
        self.assertFalse(card.update("downloading"))
        bot.message.assert_called_once()

    def test_stage_publisher_does_not_leak_unstructured_fields(self):
        env={"GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":"zwthys-cyber/ipa-decrypt-lab",
             "GITHUB_RUN_ID":"123","GITHUB_SHA":"f"*40,"GH_TOKEN":"synthetic-only"}
        with patch.dict("os.environ",env,clear=True), patch("telegram_queue.GitHub") as factory:
            api=factory.return_value
            api.call.return_value={"id":55}
            worker=WorkerProgress(RID)
            worker.advance("downloading")
            worker.advance("decrypting")
            calls=api.call.call_args_list
            self.assertEqual(calls[0].args[0],"/check-runs")
            self.assertEqual(calls[1].args[0],"/check-runs/55")
            payload=json.loads(calls[1].args[1]["output"]["summary"])
            self.assertEqual(set(payload),{"schema","request_id","run_id","stage"})
            self.assertEqual(payload["stage"],"decrypting")

    def test_ambiguous_progress_post_is_not_repeated(self):
        env={"GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":"zwthys-cyber/ipa-decrypt-lab",
             "GITHUB_RUN_ID":"123","GITHUB_SHA":"f"*40,"GH_TOKEN":"synthetic-only"}
        with patch.dict("os.environ",env,clear=True), patch("telegram_queue.GitHub") as factory:
            api=factory.return_value;api.call.side_effect=RuntimeError("private")
            worker=WorkerProgress(RID)
            worker.advance("downloading");worker.advance("decrypting")
            api.call.assert_called_once()

if __name__=="__main__":
    unittest.main()
