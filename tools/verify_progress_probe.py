"""Read back only the current run's synthetic, non-private progress snapshots."""
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path
from task_progress import parse_snapshot
from telegram_queue import GitHub, sha256

api=GitHub(os.environ["GH_TOKEN"])
run=os.environ["GITHUB_RUN_ID"]
commit=os.environ["GITHUB_SHA"]
rid="f"*32
items=api.call("/actions/runs/"+run+"/artifacts?per_page=100")["artifacts"]
stages=set()
counters=[]
for item in items:
    match=re.fullmatch("progress-"+rid+r"-([0-9]{1,10})",item["name"])
    if not match or item["expired"]: continue
    assert 0<item["size_in_bytes"]<=65536
    with tempfile.TemporaryDirectory() as directory:
        archive=Path(directory)/"snapshot.zip"
        api.archive(item["id"],archive,max_bytes=65536)
        assert "sha256:"+sha256(archive)==item["digest"]
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.namelist()==["progress.json"]
            assert zipped.getinfo("progress.json").file_size<=2048
            value=parse_snapshot(json.loads(zipped.read("progress.json")),rid,run,commit,int(match.group(1)))
            assert value is not None
    stages.add(value["stage"])
    if value.get("measurement"):counters.append(value["measurement"]["completed"])
assert {"downloading","artifact_ready"}<=stages
assert any(0<value<1024 for value in counters)
result={"schema":"ipa-progress-snapshot-probe-v1","status":"verified","snapshots":len([i for i in items if i["name"].startswith("progress-"+rid)]),"measured_counters":sorted(set(counters)),"private_credentials_used":False,"telegram_file_sent":False}
Path("progress-probe.json").write_text(json.dumps(result)+"\n")
print(json.dumps(result))
