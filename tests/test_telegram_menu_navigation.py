import copy
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from telegram_controller import Controller
from telegram_menu import COMMANDS

OWNER=123456789

class MenuNavigationTests(unittest.TestCase):
    def setUp(self):
        self.bot=Mock()
        self.gh=Mock()
        self.c=Controller(self.bot,self.gh,OWNER,"crypt","synthetic")
    def callback(self,page):
        return {"update_id":3,"callback_query":{"id":"menu-query","data":"menu:"+page,
            "from":{"id":OWNER,"is_bot":False},
            "message":{"message_id":77,"from":{"id":999,"is_bot":True},
                       "chat":{"id":OWNER,"type":"private"}}}}
    def test_home_has_two_buttons_without_quota_and_legacy_commands_remain_hidden(self):
        self.c.handle({"update_id":1,"message":{"date":int(time.time()),"text":"/start",
            "from":{"id":OWNER,"is_bot":False},"chat":{"id":OWNER,"type":"private"}}})
        method,payload=self.bot.call.call_args.args
        self.assertEqual(method,"sendMessage")
        self.assertEqual([b["callback_data"] for row in payload["reply_markup"]["inline_keyboard"] for b in row],
                         ["menu:versions","menu:help"])
        self.assertEqual([c["command"] for c in COMMANDS],["start","status","cancel"])
        self.gh.dispatch.assert_not_called()
    def test_navigation_replaces_same_message_without_querying_or_submitting(self):
        for page in ("versions","home","help","home"):
            self.c.handle(self.callback(page))
            method,payload=self.bot.call.call_args.args
            self.assertEqual(method,"editMessageText")
            self.assertEqual(payload["message_id"],77)
            self.assertEqual(payload["chat_id"],OWNER)
        self.assertEqual(self.gh.mock_calls,[])
    def test_foreign_and_nonprivate_callbacks_cannot_edit_menu(self):
        variants=[]
        bad=self.callback("help");bad["callback_query"]["from"]["id"]=OWNER+1;variants.append(bad)
        bad=self.callback("help");bad["callback_query"]["message"]["chat"]["type"]="group";variants.append(bad)
        bad=self.callback("help");bad["callback_query"]["message"]["from"]["is_bot"]=False;variants.append(bad)
        for value in variants:
            self.c.handle(value)
        self.bot.call.assert_not_called()
        self.assertEqual(self.gh.mock_calls,[])
