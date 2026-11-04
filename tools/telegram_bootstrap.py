"""Bounded identity bootstrap; no Apple access and no job submission."""
import argparse
import json
import os
import time
from telegram_api import APIError, Telegram, private_message

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=("check", "identify"), default="check")
    args = p.parse_args()
    try:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            raise APIError("requires_github_actions")
        bot = Telegram(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
        bot.check()
        print(json.dumps({"schema": "telegram-bootstrap-v1", "status": "bot_identity_verified",
                          "bot_username": "ipazake_bot"}), flush=True)
        if args.mode == "check":
            return 0
        started = time.time()
        deadline = time.monotonic() + 600
        offset, seen, replies = 0, set(), 0
        while time.monotonic() < deadline and len(seen) < 100:
            updates = bot.call("getUpdates", {"offset": offset, "limit": 20, "timeout": 20,
                                              "allowed_updates": ["message"]})
            if not isinstance(updates, list):
                raise APIError("telegram_invalid_response")
            for update in updates:
                if not isinstance(update, dict) or type(update.get("update_id")) is not int:
                    continue
                offset = max(offset, update["update_id"] + 1)
                item = private_message(update)
                if not item:
                    continue
                uid, text, date = item
                if date < started - 60 or uid in seen or text not in ("/start", "/id", "/id@ipazake_bot"):
                    continue
                seen.add(uid)
                bot.message(uid, "你的 Telegram 数字用户 ID：\n" + str(uid) +
                            "\n\n请把这串数字发回项目对话。当前仅开启身份查询，尚未开放 IPA 任务。")
                replies += 1
                print(json.dumps({"schema": "telegram-bootstrap-v1", "status": "identity_replied",
                                  "reply_count": replies}), flush=True)
        print(json.dumps({"schema": "telegram-bootstrap-v1", "status": "session_finished",
                          "reply_count": replies}), flush=True)
        return 0
    except APIError as exc:
        print(json.dumps({"schema": "telegram-bootstrap-v1", "status": exc.status}), flush=True)
        return 2
    except Exception:
        print('{"schema":"telegram-bootstrap-v1","status":"bootstrap_failed"}', flush=True)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
