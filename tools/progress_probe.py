"""Account-free progress transport fixture; never submits or delivers an IPA."""
import os
import time
from task_progress import WorkerProgress

if any(os.environ.get(key) for key in ("APPLE_ID","APPLE_PASSWORD","FAIRPLAY_MODEL_B64","DELIVERY_AGE_IDENTITY","TELEGRAM_BOT_TOKEN")):
    raise SystemExit("probe_received_private_credentials")
assert os.environ.get("DELIVERY_REQUEST_ID")=="f"*32
worker=WorkerProgress("f"*32)
worker.advance("metadata")
time.sleep(6)
worker.advance("downloading")
for completed in (0,512,1024):
    worker.measure(completed,1024)
    time.sleep(6)
worker.advance("decrypting")
time.sleep(6)
worker.advance("artifact_ready")
