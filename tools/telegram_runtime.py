"""Temporary official Bot API server, bound only to loopback."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from telegram_api import APIError, Telegram

@contextmanager
def local_bot(binary):
    token = os.environ.get("TELEGRAM_BOT_TOKEN","")
    api_id, api_hash = os.environ.get("TELEGRAM_API_ID",""), os.environ.get("TELEGRAM_API_HASH","")
    if not re.fullmatch(r"[1-9][0-9]{4,10}",api_id) or not re.fullmatch(r"[a-fA-F0-9]{32}",api_hash):
        raise APIError("missing_or_invalid_telegram_app_credentials")
    cloud = Telegram(token)
    try:
        cloud.check()
        if cloud.call("logOut") is not True:
            raise APIError("cloud_logout_unconfirmed")
    except APIError as exc:
        # Cloud login is unavailable for 10 minutes after a successful migration.
        # Local getMe must independently authenticate before any owner message.
        if exc.status != "telegram_rate_limited":
            raise
    with tempfile.TemporaryDirectory(prefix="telegram-local-private-") as directory:
        root = Path(directory)
        root.chmod(0o700)
        env = {k:os.environ[k] for k in ("PATH","LANG") if k in os.environ}
        env.update(HOME=str(root), TELEGRAM_API_ID=api_id, TELEGRAM_API_HASH=api_hash)
        with open(root/"server.log","wb") as log:
            process = subprocess.Popen([str(Path(binary).resolve()),"--local",
                "--http-ip-address=127.0.0.1","--http-port=8081","--verbosity=0",
                "--dir="+str(root/"state"),"--temp-dir="+str(root/"temp")],
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            bot = Telegram(token,"http://127.0.0.1:8081")
            authenticated = False
            try:
                deadline = time.monotonic()+120
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise APIError("local_bot_server_exited")
                    try:
                        bot.check()
                        authenticated = True
                        break
                    except APIError as exc:
                        if exc.status in ("invalid_bot_token","unexpected_bot_identity",
                                         "existing_webhook_requires_resolution"):
                            raise
                        time.sleep(2)
                if not authenticated:
                    raise APIError("local_bot_server_not_ready")
                yield bot
            finally:
                if authenticated:
                    try:
                        bot.call("logOut", timeout=30)
                    except APIError:
                        # Server state/logs remain private and are destroyed below.
                        pass
                process.terminate()
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
