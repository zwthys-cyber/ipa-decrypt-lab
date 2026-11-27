# Telegram 使用说明

更新于 2026-11-27，适用于原机器人已切换的 Cloudflare / CircleCI 入口。仅接受配置主人的私聊，完成后发送私有 Google Drive 链接。原运行环境 的白名单、文件附件和进度卡行为不作为新入口说明。

## 支持的输入

| 输入 | 行为 |
| --- | --- |
| App Store 完整 HTTPS 链接或数字 App ID | 提交最新版 |
| /start 或 /help | 使用说明 |
| /versions AppStore链接或AppID | 查询历史版本，完成后发送可点选按钮 |
| /version AppStore链接或AppID 版本号 | 指定版本；也接受 Apple externalVersionID |
| /status | 查看最近 5 条新运行时任务的已提交状态 |
| /get pilot_任务编号 | 核验并领取自己的未过期私有文件 |
| /cancel pilot_任务编号 | 记录取消请求，等待工作机终止确认 |
| 完整 TestFlight 邀请链接 | 进入已接入的新 TF 处理路径；新平台真实 TF 请求仍待单独验收 |

`/latest`、`/decrypt`、`/id`、`/allow`、`/deny`、`/users` 及不带任务编号的 `/get`、`/cancel` 均未在当前入口实现。Telegram 旧消息、菜单或截图可能仍显示旧界面，以本表和实际新回复为准。

任务对外编号为 `pilot_` 加 32 位摘要，不再以旧 cn_/tf_ 内部请求号作为 /get 参数。/status 只读一次状态快照，不会逐条启动外部请求。

## 地区和历史版本

- 完整 `https://apps.apple.com/cn/app/id6745890963` 使用国区；其他地区链接及裸数字使用默认外区。
- 国区查询及指定版本要保留 /cn/，不能改成裸 ID。
- /versions 每页最多 10 项，最多 20 页，缓存 24 小时，按钮 6 小时有效；一次列表家族只能选择一个版本。
- 首次/刷新远程查询至少间隔 60 秒，更早页面至少 5 秒；目录查询每 UTC 日最多 20 次。翻阅已确认缓存不重新启动原生查询。
- 找不到版本、地区许可拒绝或版本不符时停止，不回退最新版或另一账号。当前不提供 Bundle ID 入口；TestFlight 不支持 App Store 历史命令。

示例仅说明语法，不会自动提交：

```text
/versions https://apps.apple.com/cn/app/id1661733229
/version https://apps.apple.com/cn/app/id1661733229 1.18.1
/get pilot_<32位任务摘要>
/cancel pilot_<32位任务摘要>
```

历史目录/点选及 TF 的控制流程已接入、通过 CI；新平台真实历史交付和新 TF 请求尚未验收。旧平台历史记录见[国区说明](CHINA-ACCOUNT.md)、[TF 记录](TESTFLIGHT.md)。

## 文件和任务

当前 IPA 上限 2,000,000,000 字节。任务串行、工作机按需启动，排队时间取决于 CircleCI；数量受部署额度限制，失败和取消也可能消耗当天提交额度。

下载、严格 CodeDirectory 页面核验、账号数据清理、私有上传及控制面文件校验完成后，机器人发送“打开私有文件”按钮。以自己的 Google 账号访问；不会发送公开网盘链接。/get 的领取窗口当前为注册后 24 小时，不等于 Drive 文件授权到期。

新版没有承诺原运行环境 五秒计时进度卡或每阶段百分比。/status 显示最近一次已提交状态；通知超时或结果不明不会自动再发。不要连续重发同一链接来检查进度。确认失败并修复后，由主人提交新请求，不自动重放原任务。

## 实测及维护

红果漫剧6745890963在 CircleCI75通过17个加密镜像/120,976页、342,632,968字节的完整明文及私有交付检查；机器人通知得到确认，全程约4分23秒（含约50秒排队）。Go Club的已确认私有文件继续保留，不重复下载。/status用户截图曾观测到约1秒回复；这些均为单次样本。

会话维护与日常任务分开，普通国区任务不自动密码登录或新增授权。当前支持范围、分支和维护顺序见[运行手册](OPERATIONS.md)与[项目状态](PROJECT-STATUS.md)。历史VPS用户说明可从[固定源码档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/185a52110922e0f67ac2c7dff4e1fa85b3b4c98e/docs/TELEGRAM.md)追溯。
