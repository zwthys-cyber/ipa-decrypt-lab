"""Persistent Chinese command menu for the configured owner's private chat."""
from telegram_api import APIError

COMMANDS = [
    {"command":"latest", "description":"下载最新版：发送 App Store 链接或 ID"},
    {"command":"version", "description":"下载旧版：/version AppID 版本号"},
    {"command":"status", "description":"查看当前任务进度"},
    {"command":"get", "description":"按任务编号取回已完成文件"},
    {"command":"cancel", "description":"取消当前任务"},
    {"command":"help", "description":"查看使用说明"},
    {"command":"id", "description":"查看我的 Telegram 数字 ID"},
    {"command":"start", "description":"打开机器人使用指南"},
]

def configure(bot, owner):
    if type(owner) is not int or owner <= 0:
        raise APIError("invalid_menu_owner")
    scope = {"type":"chat", "chat_id":owner}
    # Explicit Chinese and the fallback locale cover Chinese and other clients.
    for language in ("", "zh"):
        payload = {"scope":scope,"language_code":language,"commands":COMMANDS}
        if bot.call("setMyCommands",payload) is not True:
            raise APIError("telegram_menu_write_unconfirmed")
        actual = bot.call("getMyCommands",{"scope":scope,"language_code":language})
        if actual != COMMANDS:
            raise APIError("telegram_menu_readback_mismatch")
    if bot.call("setChatMenuButton",{"chat_id":owner,"menu_button":{"type":"commands"}}) is not True:
        raise APIError("telegram_menu_button_unconfirmed")
    if bot.call("getChatMenuButton",{"chat_id":owner}) != {"type":"commands"}:
        raise APIError("telegram_menu_button_readback_mismatch")
    return {"status":"telegram_menu_verified","command_count":len(COMMANDS),
            "languages":["default","zh"],"button_type":"commands"}
