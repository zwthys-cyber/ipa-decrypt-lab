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
        self.assertEqual(alternate([job()]),"macos-15-intel")
        j=job();j["labels"]=["macos-15-intel"]
        self.assertEqual(alternate([j]),"macos-15")
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
        self.assertEqual(post.args[1]["inputs"]["runner"],"macos-15-intel")
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
