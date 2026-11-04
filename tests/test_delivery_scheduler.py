import copy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from delivery_scheduler import matches, app_from_run, queued_too_long, retryable, alternate
from telegram_queue import GitHub, QueueError
from telegram_session import Controller

RID="a"*32
def job():
    return {"status":"completed","runner_id":None,"runner_name":"","steps":[],"labels":["macos-15"]}
def old():
    return {"id":10,"status":"completed","conclusion":"failure","head_branch":"main",
            "event":"workflow_dispatch","path":".github/workflows/private-delivery.yml",
            "display_title":"delivery-"+RID}

class SchedulerTests(unittest.TestCase):
    def test_retries_only_failure_before_assignment(self):
        run=old()
        self.assertTrue(retryable(run,[job()]))
        self.assertFalse(retryable(run,[]))
        for field,value in (("runner_id",99),("runner_name","runner"),
                            ("steps",[{"name":"download"}]),("status","in_progress")):
            j=job();j[field]=value
            self.assertFalse(retryable(run,[j]),field)
        run["conclusion"]="cancelled"
        self.assertFalse(retryable(run,[job()]))
        self.assertTrue(retryable(run,[job()],cancel_requested=True))
        run["status"]="in_progress"
        self.assertFalse(retryable(run,[job()],cancel_requested=True))

    def test_queue_timeout_is_based_on_creation_and_no_runner(self):
        run={"status":"queued","created_at":"2026-11-04T00:00:00Z"}
        now=datetime(2026,11,4,0,3,tzinfo=timezone.utc)
        self.assertTrue(queued_too_long(run,[job()],now))
        self.assertFalse(queued_too_long(run,[job()],now.replace(minute=2)))
        run["status"]="in_progress"
        self.assertFalse(queued_too_long(run,[job()],now))

    def test_runner_and_legacy_metadata(self):
        self.assertEqual(alternate([job()]),"macos-26-intel")
        j=job();j["labels"]=["macos-15-intel"]
        self.assertEqual(alternate([j]),"macos-26-intel")
        j["labels"]=["macos-26-intel"]
        self.assertEqual(alternate([j]),"macos-15-intel")
        run=old()
        self.assertTrue(matches(run,RID))
        run["display_title"]="delivery-"+RID+"-app1530340312-macos-15-intel"
        self.assertTrue(matches(run,RID))
        self.assertEqual(app_from_run(run,RID),"1530340312")
        run["display_title"]+=";command"
        self.assertFalse(matches(run,RID))

    def test_build_progress_is_available_before_worker_feed(self):
        api=GitHub("synthetic")
        api.call=Mock(return_value={"check_runs":[]})
        api.jobs=Mock(return_value=[{"steps":[{"name":"Test independent signing request construction",
                                               "status":"in_progress"}]}])
        self.assertEqual(api.progress({"id":10,"head_sha":"f"*40},RID),"building")

    def test_verified_result_wins_over_failed_retry(self):
        api=GitHub("synthetic")
        successful=dict(old(),id=8,conclusion="success")
        api.runs=Mock(return_value=[old(),successful])
        self.assertEqual(api.find(RID)["id"],8)

    def test_retry_uses_alternate_pool_after_terminal_proof(self):
        api=GitHub("synthetic")
        api.runs=Mock(return_value=[old()])
        api.jobs=Mock(return_value=[job()])
        api.call=Mock(side_effect=[old(),{"workflow_run_id":11}])
        api.retry("1530340312",RID,10)
        post=api.call.call_args
        self.assertEqual(post.args[2],"POST")
        self.assertEqual(post.args[1]["inputs"]["runner"],"macos-26-intel")
        api.runs.return_value=[dict(old(),id=11,status="queued"),old()]
        api.retry("1530340312",RID,10)
        self.assertEqual(api.call.call_count,2)

    def test_no_retry_when_execution_or_budget_is_uncertain(self):
        api=GitHub("synthetic")
        api.runs=Mock(return_value=[old(),dict(old(),id=9)])
        api.call=Mock()
        with self.assertRaises(QueueError):
            api.retry("1530340312",RID,10)
        api.call.assert_not_called()

    def test_early_delivery_requires_bound_ready_feed_and_finalized_artifact(self):
        run=dict(old(),status="in_progress",conclusion=None)
        api=GitHub("synthetic")
        api.progress=Mock(return_value="artifact_ready")
        artifact={"id":55,"name":"delivery-"+RID,"expired":False,"size_in_bytes":200,
                  "digest":"sha256:"+"b"*64}
        api.call=Mock(return_value={"artifacts":[artifact]})
        self.assertTrue(api.artifact_ready(run,RID))
        for key,value in (("expired",True),("digest",""),("size_in_bytes",0),("name","other")):
            item=dict(artifact);item[key]=value
            api.call.return_value={"artifacts":[item]}
            self.assertFalse(api.artifact_ready(run,RID),key)
        api.call.return_value={"artifacts":[artifact]}
        api.progress.return_value="encrypting"
        self.assertFalse(api.artifact_ready(run,RID))
        api.progress.return_value="artifact_ready"
        self.assertFalse(api.artifact_ready(dict(run,status="completed",conclusion="failure"),RID))
        self.assertFalse(api.artifact_ready(dict(run,head_branch="other"),RID))

    def test_ready_artifact_delivers_once_while_ci_status_is_delayed(self):
        bot,api=Mock(),Mock()
        api.find.return_value=dict(old(),status="in_progress",conclusion=None)
        api.artifact_ready.return_value=True
        api.deliver.return_value={"status":"telegram_file_delivered","request_id":RID,"bytes":200}
        c=Controller(bot,api,123,"/crypt","synthetic")
        c.current={"rid":RID,"app":"1530340312","state":"in_progress"}
        c.tick();c.tick()
        api.deliver.assert_called_once()
        self.assertIsNone(c.current)

    def test_real_stage_overrides_stale_queued_run_without_cancelling(self):
        bot,api=Mock(),Mock()
        api.find.return_value=dict(old(),status="queued",conclusion=None)
        api.progress.return_value="downloading"
        api.artifact_ready.return_value=False
        c=Controller(bot,api,123,"/crypt","synthetic")
        c.current={"rid":RID,"app":"1530340312","state":"queued"}
        c.tick()
        self.assertEqual(c.current["stage"],"downloading")
        api.cancel.assert_not_called()
        api.retry.assert_not_called()

    def test_native_check_progress_overrides_empty_delayed_jobs(self):
        api=GitHub("synthetic")
        api.jobs=Mock(return_value=[{"id":55,"steps":[]}])
        api.call=Mock(side_effect=[{"check_runs":[]},
            {"status":"in_progress","head_sha":"f"*40,"app":{"slug":"github-actions"}}])
        self.assertEqual(api.progress({"id":10,"head_sha":"f"*40},RID),"preparing")

    def test_stale_actions_metadata_cannot_cancel_a_running_native_check(self):
        api=GitHub("synthetic")
        run=dict(old(),head_sha="f"*40)
        queued_job=dict(job(),id=55)
        api.call=Mock(return_value={"status":"in_progress","head_sha":"f"*40,
                                    "app":{"slug":"github-actions"}})
        self.assertFalse(api.queued_confirmed(run,[queued_job]))
        api.call.return_value["status"]="queued"
        self.assertTrue(api.queued_confirmed(run,[queued_job]))
        api.call.return_value["head_sha"]="e"*40
        self.assertFalse(api.queued_confirmed(run,[queued_job]))

    def test_controller_does_not_repeat_ambiguous_retry_post(self):
        bot,api=Mock(),Mock()
        api.runs.return_value=[old()]
        api.jobs.return_value=[job()]
        api.retry.side_effect=QueueError("github_transport_unknown")
        c=Controller(bot,api,123,"/crypt","synthetic")
        c.current={"rid":RID,"app":"1530340312","state":"queued"}
        self.assertTrue(c.failover(old()))
        self.assertTrue(c.failover(old()))
        api.retry.assert_called_once()

if __name__=="__main__":
    unittest.main()
