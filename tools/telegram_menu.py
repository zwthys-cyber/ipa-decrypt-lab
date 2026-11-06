"""Persistent Chinese command menu for the configured owner's private chat."""
from telegram_api import APIError

HOME_TEXT=("🤖 IPA 下载助手\n\n"
           "最新版：直接发送 App Store 链接或 App ID。\n"
           "旧版本：点击下方按钮查看用法。\n\n"
           "支持美区免费应用 · IPA 最大 2000 MB")
COMMANDS = [
    {"command":"start","description":"打开首页"},
    {"command":"status","description":"查看任务进度"},
    {"command":"cancel","description":"取消当前任务"},
]

def show_menu(bot,owner,page="home",message_id=None):
    if page=="home":
        text=HOME_TEXT
        buttons=[[{"text":"🕘 下载旧版本","callback_data":"menu:versions"},
                  {"text":"使用帮助","callback_data":"menu:help"}]]
    elif page=="versions":
        text=("🕘 下载旧版本\n\n"
              "点击选择版本：\n/versions AppID或商店链接\n\n"
              "指定版本下载：\n/version AppID或商店链接 版本号\n\n"
              "例如：\n/versions 444934666\n/version 444934666 9.3.55\n\n"
              "选中并通过检查后，版本列表会自动收起。")
        buttons=[[{"text":"‹ 返回","callback_data":"menu:home"}]]
    else:
        text=("使用帮助\n\n"
              "直接发送 App Store 链接或数字 ID，下载最新版。\n"
              "/status 查看任务进度\n"
              "/cancel 取消当前任务\n"
              "/get 任务编号 取回已完成文件\n"
              "/id 查看自己的数字 ID\n\n"
              "仅支持美区免费应用，文件最大 2000 MB。\n"
              "当前仅管理员私聊可用。")
        buttons=[[{"text":"‹ 返回","callback_data":"menu:home"}]]
    payload={"chat_id":owner,"text":text,"reply_markup":{"inline_keyboard":buttons},
             "link_preview_options":{"is_disabled":True}}
    if message_id is not None:
        payload["message_id"]=message_id
    return bot.call("editMessageText" if message_id is not None else "sendMessage",payload)

def navigation(bot,owner,update):
    query=update.get("callback_query")
    if not isinstance(query,dict) or query.get("data") not in ("menu:home","menu:versions","menu:help"):
        return False
    sender=query.get("from")
    message=query.get("message")
    if not isinstance(sender,dict) or not isinstance(message,dict):
        return True
    chat=message.get("chat")
    author=message.get("from")
    if (sender.get("id")!=owner or sender.get("is_bot") is not False
            or not isinstance(chat,dict) or chat.get("id")!=owner or chat.get("type")!="private"
            or not isinstance(author,dict) or author.get("is_bot") is not True
            or type(message.get("message_id")) is not int
            or not isinstance(query.get("id"),str) or not 0<len(query["id"])<=128):
        return True
    try:
        bot.call("answerCallbackQuery",{"callback_query_id":query["id"]})
    except APIError:
        pass
    show_menu(bot,owner,query["data"].split(":")[1],message["message_id"])
    return True


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
