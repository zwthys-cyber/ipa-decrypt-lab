import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from task_progress import ProgressCard, WorkerProgress, parse_snapshot, duration
from persistent_journal import PersistentJournal
from telegram_controller import Controller
from telegram_queue import GitHub
from progress_stream import run_download

RID="e"*32
COMMIT="a"*40

class LiveProgressContracts(unittest.TestCase):
    def snapshot(self):
        return {"schema":"ipa-stage-v2","request_id":RID,"run_id":"12","commit":COMMIT,
                "stage":"downloading","sequence":4,"updated_at":int(time.time()),
                "measurement":{"unit":"bytes","completed":512,"total":1024}}

    def test_snapshot_rejects_other_requests_replays_and_unstructured_values(self):
        item=self.snapshot()
        self.assertIsNotNone(parse_snapshot(item,RID,12,COMMIT,4))
        for key,value in (("request_id","b"*32),("run_id","13"),("commit","f"*40),
                          ("stage","raw-private-message"),("sequence",True),("updated_at",0),
                          ("password","PRIVATE_PASSWORD")):
            bad=copy.deepcopy(item);bad[key]=value
            self.assertIsNone(parse_snapshot(bad,RID,12,COMMIT,4))
        self.assertIsNone(parse_snapshot(item,RID,12,COMMIT,5))
        for values in ({"unit":"bytes","completed":True,"total":10},
                       {"unit":"bytes","completed":11,"total":10},
                       {"unit":"bytes","completed":1,"total":2_000_000_001},
                       {"unit":"bytes","completed":1,"total":10,"url":"PRIVATE_URL"}):
            bad=copy.deepcopy(item);bad["measurement"]=values
            self.assertIsNone(parse_snapshot(bad,RID,12,COMMIT,4))

    def test_total_clock_includes_prior_queue_time_and_stops_after_ack(self):
        bot=Mock();bot.message.return_value={"message_id":7}
        with patch('task_progress.time.time',return_value=200000),patch('task_progress.time.monotonic',return_value=10) as clock:
            card=ProgressCard(bot,123,RID,"333903271",started_at=200000-90061)
            card.update("uploading")
            self.assertIn("1天 01:01:01",card.render("uploading"))
            self.assertNotIn("100%",card.render("uploading"))
            clock.return_value=15
            card.pulse()
            self.assertIn("1天 01:01:06",bot.edit.call_args.args[2])
            card.update("done")
            final=card.render("done")
            clock.return_value=999
            self.assertIn("100%",final)
            self.assertIn("1天 01:01:06",card.render("done"))
            calls=bot.edit.call_count
            card.pulse()
            self.assertEqual(bot.edit.call_count,calls)
        self.assertEqual(duration(3661),"01:01:01")

    def test_byte_percentage_is_actual_and_not_whole_task_completion(self):
        bot=Mock();bot.message.return_value={"message_id":7}
        card=ProgressCard(bot,123,RID)
        card.update("downloading",measurement_value={"unit":"bytes","completed":512,"total":1024})
        self.assertIn("下载进度：50.0%",card.render("downloading"))
        card.update("downloading",force=True,measurement_value={"unit":"bytes","completed":True,"total":1})
        self.assertIn("下载进度：50.0%",card.render("downloading"))
        card.update("downloading",force=True,measurement_value={"unit":"bytes","completed":1024,"total":1024})
        self.assertIn("下载进度：100.0%",card.render("downloading"))
        self.assertNotIn("流程进度：██████████ 100%",card.render("downloading"))
        card.update("decrypting")
        self.assertNotIn("下载进度",card.render("decrypting"))
        card.update("preparing",force=True)
        self.assertEqual(card.stage,"decrypting")

    def test_recovery_reuses_the_card_and_original_creation_time(self):
        with tempfile.TemporaryDirectory() as directory:
            filename=Path(directory)/'state.sqlite3'
            with patch('persistent_journal.time.time',return_value=10000),patch('task_progress.time.time',return_value=10000),patch('task_progress.time.monotonic',return_value=100):
                journal=PersistentJournal(filename,123);journal.write(RID,"pending","333903271")
                bot=Mock();bot.message.return_value={"message_id":77}
                controller=Controller(bot,Mock(),123,"crypt","token",journal=journal)
                controller.card(RID,"333903271").update("downloading")
                journal.close()
            with patch('task_progress.time.time',return_value=10300),patch('task_progress.time.monotonic',return_value=5):
                journal=PersistentJournal(filename,123)
                bot=Mock();controller=Controller(bot,Mock(),123,"crypt","token",journal=journal)
                card=controller.card(RID,"333903271")
                card.update("downloading",force=True)
                bot.message.assert_not_called()
                self.assertEqual(bot.edit.call_args.args[:2],(123,77))
                self.assertIn("总耗时：00:05:00",bot.edit.call_args.args[2])
                journal.close()

    def test_clock_refresh_never_dispatches_or_sends_a_document(self):
        bot=Mock();bot.message.return_value={"message_id":7}
        github=Mock();controller=Controller(bot,github,123,"crypt","token")
        with patch('task_progress.time.monotonic',return_value=1) as clock:
            controller.current={"rid":RID}
            card=controller.card(RID);card.update("uploading")
            clock.return_value=7
            controller.refresh_progress()
        github.dispatch.assert_not_called();github.deliver.assert_not_called();bot.document.assert_not_called()
        self.assertEqual(bot.edit.call_args.kwargs['timeout'],8)

    def test_worker_file_survives_unavailable_checks_and_contains_only_numeric_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            filename=Path(directory)/'progress.json'
            env={"GITHUB_ACTIONS":"true","GITHUB_REPOSITORY":"zwthys-cyber/ipa-decrypt-lab",
                 "GITHUB_RUN_ID":"12","GITHUB_SHA":COMMIT,"IPA_PROGRESS_FILE":str(filename)}
            with patch.dict(os.environ,env,clear=True),patch('telegram_queue.GitHub') as factory,contextlib.redirect_stdout(io.StringIO()):
                factory.return_value.call.side_effect=RuntimeError('PRIVATE_ERROR')
                worker=WorkerProgress(RID);worker.advance('downloading');worker.measure(20,100)
                self.assertTrue(worker.disabled)
                value=json.loads(filename.read_text())
                self.assertEqual(value['measurement']['completed'],20)
                self.assertIsNotNone(parse_snapshot(value,RID,12,COMMIT,value['sequence']))
                self.assertNotIn('PRIVATE_ERROR',filename.read_text())
                self.assertEqual(filename.stat().st_mode&0o777,0o600)

    def test_private_stream_forwards_only_exact_numeric_markers(self):
        code="import sys;print('PRIVATE_LOG');print('IPA_LAB_DOWNLOAD_BYTES:2:10');print('IPA_LAB_DOWNLOAD_BYTES:1:10');print('IPA_LAB_DOWNLOAD_BYTES:11:10');print('IPA_LAB_DOWNLOAD_BYTES:PRIVATE:10');print('IPA_LAB_DOWNLOAD_BYTES:10:10');sys.stderr.write('PRIVATE_STDERR')"
        samples=[]
        with contextlib.redirect_stdout(io.StringIO()) as public:
            result=run_download(sys.executable,['-u','-c',code],dict(os.environ),10,lambda done,total:samples.append((done,total)))
        self.assertEqual(result.returncode,0)
        self.assertEqual(samples,[(2,10),(10,10)])
        self.assertIn('PRIVATE_LOG',result.stdout)
        self.assertEqual(public.getvalue(),'')
        with self.assertRaises(subprocess.TimeoutExpired):
            run_download(sys.executable,['-c','import time;time.sleep(10)'],dict(os.environ),0.2,lambda *args:None)

    def test_artifact_progress_works_without_checks_read_and_caches_immutable_snapshot(self):
        api=GitHub('synthetic')
        api.checks_readable=False
        item=self.snapshot()
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'fixture.zip'
            with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr('progress.json',json.dumps(item))
            raw=archive.read_bytes()
        artifact={"id":55,"name":"progress-"+RID+"-000004","expired":False,"size_in_bytes":len(raw),"digest":"sha256:"+hashlib.sha256(raw).hexdigest()}
        api.call=Mock(return_value={"artifacts":[artifact]})
        api.archive=Mock(side_effect=lambda identifier,target,**kwargs:target.write_bytes(raw))
        run={"id":12,"head_sha":COMMIT,"head_branch":"main","event":"workflow_dispatch","path":".github/workflows/private-delivery.yml"}
        self.assertEqual(api.progress(run,RID),'downloading')
        self.assertEqual(api.last_progress[RID]['measurement']['completed'],512)
        self.assertEqual(api.progress(run,RID),'downloading')
        api.archive.assert_called_once()
        self.assertIsNone(api.progress_snapshot(dict(run,head_branch='other'),RID))

if __name__=='__main__':unittest.main()
