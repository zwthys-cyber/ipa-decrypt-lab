# 使用指南

机器人通过私聊接收请求。任务完成后会发送文件入口，使用自己的 Google 账号即可访问。

## 下载最新版

直接发送 App Store 链接或数字 App ID，例如：

```text
https://apps.apple.com/cn/app/id6745890963
```

链接中的地区决定使用哪个账号：带 `/cn/` 的完整链接使用国区账号；其他地区链接和数字 ID 使用默认账号。应用是否可获取，还取决于所在商店、账号许可和版本可用性。

当前处理免费应用，IPA 上限为 2,000,000,000 字节。

## 查询历史版本

发送：

```text
/versions https://apps.apple.com/cn/app/id1661733229
```

机器人返回版本列表后，点击所需版本即可提交。列表支持翻页和刷新；一次列表只能选择一个版本。每页最多 10 项，最多 20 页，缓存保留 24 小时，按钮有效期为 6 小时。

已知版本号时，也可直接指定：

```text
/version https://apps.apple.com/cn/app/id1661733229 1.18.1
```

版本参数也接受 Apple 历史版本 ID。国区请求请保留完整 `/cn/` 链接。目标版本不可用或校验不符时，任务会停止。

历史版本在当前平台上的完整交付仍待实测，进度见[项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。

## 查看与管理任务

发送 `/start` 打开首页：

| 入口 | 用途 |
| --- | --- |
| 进行中 | 查看排队、处理或上传中的任务 |
| 已完成 | 查看已完成任务并领取文件 |
| 历史记录 | 查看已取消的任务；已结束的未完成条目不在列表显示 |
| 使用帮助 | 查看常用操作 |

任务列表每页最多 3 项。翻页和刷新会更新当前消息，文件按钮显示应用名称。尚未取得名称的任务会先显示地区和 App ID。

发送 `/status` 可直接查看任务；没有进行中的任务时，会显示已完成列表。取消操作可使用任务按钮，或手动发送 `/cancel 任务编号`。

## 领取文件

点击已完成应用的名称，再点击“打开文件”。文件保持私有权限，需要使用自己的 Google 账号登录。

手动领取可使用 `/get 任务编号`。领取窗口目前为文件注册后的 24 小时；窗口结束不自动撤销 Google Drive 权限。

请保留任务编号用于故障核对。已完成、已取消或发送结果不明的任务不会自动重新执行。

## TestFlight

直接发送完整邀请链接：

```text
https://testflight.apple.com/join/<邀请码>
```

该入口使用独立的保存会话，不支持 App Store 历史版本参数。当前平台的新 TestFlight 任务仍待实测，详见[TestFlight 说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TESTFLIGHT.md)。

## 回复与处理状态

准备回复时，聊天顶部可能短暂显示“正在输入…”。回复送达后，Telegram 会清除这个提示。长时间运行的任务请通过任务列表查看；顶部提示不代表下载进度。

工作机按需启动，排队、应用大小和网络都会影响耗时。出现失败时，先保留任务编号并核对原因，修复后再提交新请求。

全部受支持的手动指令为 `/start`、`/help`、`/status`、`/history`、`/versions`、`/version`、`/get` 和 `/cancel`。`/get`、`/cancel` 需要完整任务编号。
