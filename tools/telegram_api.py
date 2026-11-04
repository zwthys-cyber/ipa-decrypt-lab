"""Small Telegram client. Never print API URLs, payloads or raw errors."""
import http.client
import json
import re
import urllib.error
import urllib.request

class APIError(RuntimeError):
    def __init__(self, status="telegram_unavailable"):
        super().__init__(status)
        self.status = status

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Telegram:
    def __init__(self, token, base="https://api.telegram.org"):
        if not re.fullmatch(r"[0-9]{5,20}:[A-Za-z0-9_-]{20,80}", token or ""):
            raise APIError("invalid_bot_token")
        if base not in ("https://api.telegram.org", "http://127.0.0.1:8081"):
            raise APIError("invalid_telegram_endpoint")
        self.token, self.base = token, base
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, method, payload=None, timeout=40):
        if method not in {"getMe", "getWebhookInfo", "getUpdates", "sendMessage",
                          "sendDocument", "logOut", "close"}:
            raise APIError("unsupported_telegram_method")
        data = json.dumps(payload or {}, ensure_ascii=True).encode()
        request = urllib.request.Request(self.base + "/bot" + self.token + "/" + method,
                                         data=data, headers={"Content-Type": "application/json"},
                                         method="POST")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            return self.parse(raw)
        except urllib.error.HTTPError as exc:
            status = {401: "invalid_bot_token", 409: "telegram_polling_conflict",
                      429: "telegram_rate_limited"}.get(exc.code, "telegram_request_rejected")
            exc.close()
            raise APIError(status) from None
        except (OSError, ValueError, http.client.HTTPException):
            raise APIError("telegram_transport_unknown") from None

    @staticmethod
    def parse(raw):
        if len(raw) > 2 * 1024 * 1024:
            raise APIError("telegram_response_too_large")
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("ok") is not True:
                raise APIError("telegram_request_rejected")
            return data["result"]
        except (KeyError, ValueError, TypeError):
            raise APIError("telegram_invalid_response") from None

    def check(self):
        me = self.call("getMe")
        if not isinstance(me, dict) or me.get("is_bot") is not True or me.get("username") != "ipazake_bot":
            raise APIError("unexpected_bot_identity")
        hook = self.call("getWebhookInfo")
        if not isinstance(hook, dict) or hook.get("url"):
            raise APIError("existing_webhook_requires_resolution")
        return True

    def message(self, chat, text):
        result = self.call("sendMessage", {"chat_id": chat, "text": text,
                           "link_preview_options": {"is_disabled": True}})
        if not isinstance(result, dict) or type(result.get("message_id")) is not int:
            raise APIError("telegram_send_unconfirmed")
        return result

def private_message(update):
    if not isinstance(update, dict) or type(update.get("update_id")) is not int:
        return None
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    sender, chat = message.get("from"), message.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return None
    uid = sender.get("id")
    if (type(uid) is not int or uid <= 0 or sender.get("is_bot") is not False
            or chat.get("type") != "private" or chat.get("id") != uid
            or type(message.get("date")) is not int
            or not isinstance(message.get("text"), str) or len(message["text"]) > 1024):
        return None
    return uid, message["text"].strip(), message["date"]
