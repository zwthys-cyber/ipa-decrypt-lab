import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from telegram_api import APIError, Telegram, private_message

def update(uid=12345, text="/id"):
    return {"update_id": 20, "message": {"date": 1234, "from": {"id": uid, "is_bot": False},
            "chat": {"id": uid, "type": "private"}, "text": text}}

class TelegramBoundaryTests(unittest.TestCase):
    def test_private_sender(self):
        self.assertEqual(private_message(update()), (12345, "/id", 1234))
        for field, value in (("type", "group"), ("id", 8765)):
            u = update()
            u["message"]["chat"][field] = value
            self.assertIsNone(private_message(u))
        u = update()
        u["message"]["from"]["is_bot"] = True
        self.assertIsNone(private_message(u))

    def test_malformed_and_overlong(self):
        for value in (None, {}, {"update_id": True}, update(True), update(text="x" * 1025)):
            self.assertIsNone(private_message(value))

    def test_invalid_response_does_not_echo_raw_body(self):
        for value in (b"secret", b'{"ok":false,"description":"secret"}', b'{}'):
            with self.assertRaises(APIError) as caught:
                Telegram.parse(value)
            self.assertNotIn("secret", str(caught.exception))

    def test_endpoint_and_token_guard(self):
        with self.assertRaises(APIError):
            Telegram("fake")
        with self.assertRaises(APIError):
            Telegram("123456:" + "A" * 35, "https://example.com")

if __name__ == "__main__":
    unittest.main()
