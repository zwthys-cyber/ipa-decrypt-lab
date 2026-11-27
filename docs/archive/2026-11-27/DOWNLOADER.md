> 历史资料归档 · 2026-11-27
>
> 本文保留归档时的实验、判断与验证记录。日常使用见[使用指南](../../TELEGRAM.md)，当前范围见[项目状态](../../PROJECT-STATUS.md)。[原始来源](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/977b239ee2e35c908361109c8d0e10d1fa252873/docs/DOWNLOADER.md)。

# 下载、验证与私有交付

更新于2026-11-27。生产处理源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`，原机器人通过Cloudflare/D1接入CircleCI macOS ARM64工作机，完成后发私有Drive链接。旧private-delivery、china-private-delivery、testflight-private-delivery、version-catalog、china-version-catalog共5个工作流已停用，不是新入口的下载路径。

## 当前App Store流程

1. 主人私聊输入严格解析的AppStore链接或数字ID，按/cn/选择原独立国区账号，其余默认外区。仅免费应用，当前IPA上限2,000,000,000字节。
2. 控制面先持久化意图，串行提交source/run/job绑定的CircleCI任务；GitHub签发短期角色信封，工作机不取得交付主私钥或Drive刷新凭据。
3. 加载pins固定的已验证ARM64公共运行包，核对来源、归档/逐文件摘要、原生输入合约及主机ABI，普通任务不编译项目。
4. 国区恢复原会话/GUID/checkpoint/model，临时HOME与CFFIXED_USER_HOME一致；日常任务不自动密码回退、新验证码、换身份或电脑授权。
5. 获取原包，绑定AppID/bundle/请求版本；复用已有模型，严格验证全部受保护页面的预加密CodeDirectory哈希，清理账号数据并核对ZIP/CRC/摘要。
6. 工作机上传私有Drive文件，控制面独立核对归属、名称、字节数、SHA-256和私有权限；只有全部通过后确认交付并向主人发送链接。未知通知不自动重复。

当前实现入口是[工作机](../../../deploy/managed/circleci/managed_worker.py)、[AppStore适配](../../../deploy/managed/circleci/appstore_worker.py)、[TF适配](../../../deploy/managed/circleci/tf_worker.py)和[控制面](../../../deploy/managed/circleci/runtime-api.mjs)。共享tools及.github/ops仍用于公共原生构建、兼容性和账号维护，不能因旧派发停用就整目录删除。

## 实际证明和边界

CircleCI75红果漫剧6745890963完成17镜像/120,976页、342,632,968字节严格明文及私有交付证明，通知已确认。GoClub已在新架构完成默认区真实任务。签名、安装和实际运行不在这些证明范围内。

/versions、/version及TF已接入，仍待新平台真实历史版本交付和新TF请求验收；旧LocalSend/CapyPlayer成功记录保持历史范围。新入口仅主人，不包含旧白名单和本地BotAPI附件发送。指令见[Telegram](../../TELEGRAM.md)，维护见[运行手册](../../OPERATIONS.md)。

国区会话维护在main的独立受控工作流执行，2026-11-27的单独授权维护已完成。会话拒绝、缓存路径、未知邀请结果与模型不兼容必须分开诊断，不能用放宽校验或换账号掩盖失败。

## 下方历史资料的范围

以下保留2026-11-03至11-10的客户端调查及原运行环境集成结论，不作为当前运行平台、派发工作流或交付方式的说明。

## 早期 Go 下载器与认证调查

`store-download.yml`（Original App Store IPA）保留为固定 ipatool 提交的受控研究入口，不是生产机器人采用的下载路径。旧 ARM 对照也不能推广成现有生产平台支持；当时旧生产仅允许macOS26/15 Intel；当前生产改为CircleCI macOS ARM64。

早期 generic BadLogin、5002、空响应与 HTTP 拒绝没有证明密码错误、账号封禁或明确双重认证要求。早期兼容对照与下载证据见[认证兼容](AUTH-COMPATIBILITY.md)和[下载结果](NATIVE-DOWNLOAD-RESULTS.md)。历史失败结论由[最新项目状态](PROJECT-STATUS.md)中的实测更新。


## 中国区账号的独立接入状态（2026-11-09）

中国区独立模型、跨运行器复用与保存状态重放均通过完整明文验证。`tools/cn_private_export.py` 使用专用会话、GUID、检查点和模型，以非交互 Cookie 刷新取得当前设备证明，再复用公共导出校验/清理/加密流程。`/cn/` 链接自动选择该固定工作流，中国区支持最新版及可获取的历史版本，其他链接仍使用原账号。普通国区任务不挂载外区凭据，不收验证码，不进行模型恢复或电脑授权；会话失效由管理员走独立维护流程。原德国区凭据、模型和安全设置保持原样。详见 [中国区接入说明](CHINA-ACCOUNT.md)。

## TestFlight 独立处理流程（2026-11-09）

TF 邀请由主人私聊提交，使用 `tf_` 请求与独立持久会话；先检查实际成员资格，必要时先记录接受意图、最多接受一次，再取得可用 iOS 构建。它不使用 App Store 免费许可或正式版作为替代。任务加载独立源码/ABI匹配的 TF SDK 与既有 CN 模型，严格验证全部加密页面并清理账号数据，最后通过原交付器发送 `名称_Beta_版本.ipa`。

[CapyPlayer 实际导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) 验证46个镜像、17,724页，用户截图确认收件。已有资格不重复接受；普通任务不密码重登、不初始化模型或新增授权。额外协议、会话失效、限流和明文校验失败时停止。详见 [TF 证据与限制](TESTFLIGHT.md)。
