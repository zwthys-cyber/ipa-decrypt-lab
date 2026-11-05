# Telegram 私有交付

@ipazake_bot 已迁移到 Debian 13 VPS 常驻运行，仅配置的管理员私聊可用，尚未开放收费或多用户服务。构建、测试、App Store 下载和 FairPlay 解密仍在 GitHub-hosted Actions 执行。

## 当前入口

- `vps-release.yml`：在 GitHub 完成测试与打包；`deploy=true` 部署成品。配置、权限、备份与回滚见 [VPS 部署说明](VPS-DEPLOYMENT.md)。
- `telegram-server-build.yml`：编译固定版本官方 Bot API，提供发布所需公开二进制缓存。
- `private-delivery.yml`：preflight 无账号构建验证；export 按 App ID 和任务编号生成加密交付产物。
- `delivery-contracts.yml`：合成加密/交付验证。已有交付密钥不得为了重试而重新生成。
- 旧限时轮询、云端身份查询、Checks 恢复实验入口已删除。不得另开同一机器人的轮询进程。

`tools/telegram_controller.py` 提供任务控制逻辑；`telegram_daemon.py` 负责常驻运行；`persistent_journal.py` 保存私有 SQLite 状态。旧会话脚本与 Checks 日志实现不再进入发布包。

## 流程与范围

管理员发送 App Store 链接或数字 ID → 提交前检查美区上架、免费状态和标注大小 → 固定 GitHub 工作流 → 账号授权下载 → 复用已保存模型解密 → 校验每个加密切片 → 清理 Store 账号元数据 → age 加密 → VPS 认证解包并复核摘要及 IPA 结构 → Telegram 私聊发送。

账号仍须具备下载许可。缺失验证材料、下载失败或摘要不匹配时拒绝交付。原始 IPA、模型、账号材料不发布到公开仓库或公开产物；公开密文保留一天。IPA 安装、签名兼容性及运行未验证。

当前一次处理一个任务，每 UTC 日默认最多 20 个提交（含失败任务），提交间隔至少 30 秒。默认 macos-26-intel，备用 macos-15-intel；只有确认原运行未执行且已终止时才能切换，每个逻辑任务最多两次。模糊提交结果不得自动重发。

## 私聊指令

| 指令 | 行为 |
| --- | --- |
| /start 或 /help | 使用说明 |
| /latest AppID或商店链接 | 下载最新版；单独点击菜单会提示输入应用 |
| /decrypt | 保留为最新版入口的兼容别名 |
| /versions AppID或商店链接 | 查询历史版本并显示可点击、可翻页的按钮 |
| /version AppID或商店链接 版本号 | 实时请求指定旧版，例如 `/version 444934666 9.3.55`；也接受 Apple 历史版本 ID |
| App Store 链接或数字 ID | 默认创建最新版任务 |
| /id | 显示管理员自己的数字 ID |
| /status | 查看当前任务 |
| /cancel | 请求取消当前任务 |
| /get 任务编号 | 显式取回尚未过期的完成文件 |

菜单由常驻服务启动时注册并读回核对，不再单独运行旧 menu 会话。SQLite 保存更新处理意图和任务状态；重启恢复跟踪，不重复提交下载。发送结果不明时不会自动重发，应先确认聊天再使用 /get。[恢复规则](SESSION-RECOVERY.md)。

## 进度与交付

同一张进度卡显示真实阶段、任务编号与已用时间。同阶段约 15 秒刷新，/status 可主动刷新。上传接口没有可靠逐字节回调，因此不估算进度百分比；仅 Telegram 确认文件发送成功后显示 100%。

Checks 读取无权限时使用 Actions 任务与步骤信息；缺少可信 Checks 证据时，不提前交付或主动取消排队任务，等待工作流正常完成后验证。存在可信且绑定请求/运行/提交的 artifact_ready check 时，仍须验证已完成加密产物和所有摘要才能提前交付。

当前 IPA 上限为 2000 MB（2,000,000,000 字节），使用流式审计，交付前检查约 8.15 GB 可用磁盘。QQ（444934666）已通过流式审计及真实解密导出：19 切片、131440 页，341766793 字节；本轮 Telegram 文件发送仍需单独确认，见项目状态。普通重启保留本地 Bot API 状态，不重复执行云端迁移或 logOut。

## 配置与证据

Apple 账号、已有模型、Telegram 凭据与交付私钥均配置为 GitHub Secrets；VPS 仅持有 Telegram、交付密钥及限定仓库的 GitHub token。详细名称见 [部署文档](VPS-DEPLOYMENT.md)，公钥配置在 config/delivery.json。

- [真实大文件交付 41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：92,118,013 字节，Telegram 文件确认。
- [macOS 26 样本 41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)：6 切片、164 页，验证构建缓存复用。
- [初次 VPS 部署 41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076)：Ubuntu、Debian 13、Go 与 systemd 凭据验证通过，服务启动和 Telegram 通知成功。

这些历史样本不等于迁移后新 IPA 任务已经实测。当前状态见 [项目状态](PROJECT-STATUS.md)。

最新流式审计部署：[41907700244](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907700244)，352 项测试（1 项跳过）；[QQ 真实导出 41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)通过。

## 当前容量：2000 MB

用户将直传上限定为 **2,000,000,000 字节（十进制 2000 MB）**，不支持 4 GB IPA，不启用分卷或下载链接。官方本地 Bot API 支持上传至 2000 MB，见 [Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

容量由 `tools/capacity.py` 统一定义：IPA 与单 Mach-O 上限均为 2,000,000,000 字节，Mach-O 总读取预算 4,000,000,000 字节，归档展开预算 6,000,000,000 字节，条目上限 32768。密文及外层 ZIP 另留明确封装开销；发送前再次执行严格明文大小检查。支持上限内的文件不等于所有应用均兼容。

处理前要求至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。可用应用元数据已表明超限时，在登录/下载前拒绝；元数据缺失时，下载后仍按实际大小检查。生成完成后及时删除不再需要的私有中间文件。下载超时 20 分钟、解密 15 分钟、交付加解密 10 分钟、Telegram 上传 20 分钟；GitHub worker 整体限时 70 分钟。

超限与磁盘不足通过固定 Actions 步骤标记传给机器人，使用中文提示；不读取或公开原始账号日志。发送结果未知仍不自动重发。

[发布与部署 41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129)通过 Ubuntu 和 Debian 13 各 357 项 Python 测试（1 项跳过），以及恰好 2,000,000,000 字节的 age 加密→解密→完整 SHA-256 比对和超出 1 字节拒绝测试。该大文件是 GitHub 上的合成数据，不是 2000 MB 游戏解密或 Telegram 真实上传实测。Go、systemd 凭据挂载与部署健康检查均通过。部署代码为 `4f3f79600a8f5df74c71eef6d0c03168d2895e13`。

[macOS 26 Intel 预检 41910548494](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910548494)已成功完成。独立 CMake/审计入口修复后的 [41910809719](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910809719)中 Ubuntu 与 macOS 15 Intel 已通过；记录时 ARM 任务仍在排队，不计为已通过。

## 提交前检查

机器人先显示查询提示，再检查美区上架、价格和标注大小。地区不可用、收费或已知超限时不创建 GitHub 任务、不消耗提交额度，直接显示原因。网络异常单独提示稍后重试。查询正常时通常秒级返回；超时不保证立即确认。链接的国家代码不会自动切换下载账号地区。

GitHub 手动导出也在依赖构建前检查应用条件；仍保留下载时的账号许可和实际大小校验。

## 指定历史版本（2026-11-04）

使用 `/version 444934666 9.3.55`，或 `/version 应用ID Apple历史版本ID`。第一版支持数字 App ID 和 App Store 链接，不支持 Bundle ID 输入。版本号要求数字和点；至少 6 位的非零开头纯数字按 Apple externalVersionID 处理，它不是 Info.plist 的 CFBundleVersion。

这条路径使用现有账号实时向 Apple 请求，不调用第三方解密服务或旧版 IPA 缓存。显示版本号通过 Apple 返回的历史标识列表逐项核对元数据；从较新的标识开始，最多检查 120 个，并在请求之间执行 180 秒查询时间预算检查。超过预算、账号无权访问、旧版已不可获取或查询失败会停止；可提供已知 externalVersionID 跳过列表搜索。不能承诺所有历史版本都可获取。

仍限定美区免费应用和 2000 MB 实际 IPA。旧版请求不使用最新版的商店大小作为拒绝依据，磁盘及实际文件大小检查保留。下载响应须匹配应用和 externalVersionID，原始与清理后的 IPA 均须匹配已解析显示版本。版本选择绑定工作流输入、运行标题和收据；VPS 交付再次检查版本，不回退最新版。备用线路保留同一版本，重启只恢复原任务，不重新提交。

[QQ 9.3.55 真实验证 41931938986](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41931938986)已完成指定版本下载、版本核对、20 个加密切片及 126580 页的明文校验；清理后的 IPA 为 324952532 字节。只保留一天加密交付产物，安装运行仍未验证。此运行本身不代表 Telegram 已收到文件。

[发布部署 41932870509](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41932870509)已通过两套环境各 386 项 Python 测试（1 项跳过）及健康检查，以上旧版入口已部署。

## 文件名称与图标（2026-11-04）

交付时从已校验的 IPA 根应用 Info.plist 读取 CFBundleDisplayName（缺失时使用 CFBundleName）及 CFBundleShortVersionString，文件名为“名称_版本.ipa”，例如 `QQ_9.3.55.ipa`。文件名去除控制符和路径字符并限制 UTF-8 长度；缺失字段回退 App ID / unknown。仅重命名临时文件，不改变 IPA 内容或摘要。新任务与 /get 取回已有加密产物均适用，已发送的旧附件不自动替换或重发。

优先尝试 IPA 声明的 PNG 图标，无法读取（例如仅含 Assets.car 或不支持的优化图片）时尝试 Apple 商店公开图标。商店图标可能是当前版本的图标，不保证与历史版本完全相同。图片读取限制 4 MiB、2048 像素边长，解码后缩至 320 像素内、重新编码成小于 200 kB 的 JPEG，不保留图片元数据。仅请求经核对的 App ID 和 HTTPS mzstatic.com 子域，不跟随重定向或携带账号凭据。

缩略图使用 multipart 上传，IPA 继续由本地 Bot API 读取私有文件路径，不将大 IPA 装入 HTTP 请求内存。图标获取失败时发送无缩略图文件；发送接口报错后不自动尝试无图重发，保持结果不明时的防重复规则。格式依据 [Telegram sendDocument 文档](https://core.telegram.org/bots/api#senddocument)。

[部署 41934737382](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41934737382)在 Ubuntu 和 Debian 13 各运行 396 项 Python 测试（1 项跳过），包含图标解码、中文文件名、multipart 内容和发送异常不重试检查，发布与健康检查成功。VPS 安装发行版预编译 python3-pil 运行库，不在服务器编译或运行测试。本轮尚未通过真实 Telegram 文件回执确认缩略图展示。

## 可点击历史版本列表（2026-11-05）

菜单选择 versions，或发送 `/versions 444934666`；也接受完整 App Store 链接。首次查询由固定 GitHub-hosted `version-catalog.yml` 执行，使用现有 Apple 账号读取历史标识、显示版本及 Apple 元数据中的日期字段，不下载 IPA、不访问模型 Secret。账号材料和原生响应不公开，仅发布经过严格字段检查的版本元数据，保留一天。该工作流与下载工作流串行执行。

首次查询最多核对较新的 60 个标识，在请求之间检查 180 秒预算；连续 3 个元数据查询失败停止。部分结果明确标注“非完整历史”，不会把最近版本当成全部历史。每页 10 个版本、每行 2 个按钮，支持上一页和下一页。点击某个版本即进入现有下载流程，固定使用该按钮绑定的 Apple externalVersionID。

查询结果缓存 6 小时，保留最近最多 4 个应用；翻页与缓存命中不启动 GitHub。新查询间隔至少 60 秒，每滚动 24 小时最多 20 次，不计入 IPA 下载提交额度。仅管理员私聊可查询和点击；回调绑定列表随机标识、原消息 ID 和有效期。下载选择仍受普通任务额度与单任务限制；提交前持久化按钮已使用状态，同一列表中同一按钮不重复提交。明确重新执行 /versions 可打开新的选择列表。

查询意图、缓存、列表消息 ID 和已使用按钮保存在私有 SQLite 中。重启继续跟踪已有查询，不盲目再次 dispatch；/status 显示查询状态，/cancel 可停止跟踪并请求取消查询。查询最长跟踪一小时，结果取回最多 3 次；归档下载上限 128 KiB，JSON 上限 32 KiB，并核对 SHA-256 和请求、应用、运行、提交绑定。临时归档正常结束删除，进程异常残留在启动时清理。

[部署 41940545752](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41940545752)通过 Ubuntu 与 Debian 13 各 407 项 Python 测试（1 项跳过）、Go/systemd 验证和服务健康检查。原生目录查询编译及所选 10 项 Swift 测试通过。

[机器人真实查询 41941057460](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941057460)对 App ID 6749145363 取得全部 3 个返回版本：1.0.4、1.0.3、1.0.2。线上数据库已记录 Telegram 列表消息成功回执，查询状态已结束，服务 active、NRestarts=0。随后已观察到点击 1.0.4 按钮后的真实提交：[41941946764](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941946764)，版本固定为 externalVersionID 879995305，SQLite 已持久化该按钮的使用状态。记录时下载任务仍在执行，不计为完整交付。

[QQ 复核 41941095718](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941095718)成功：Apple 返回 335 个历史标识，180 秒查询预算内取得 33 个版本，按每页 10 项可显示 4 页。首项为 9.3.80，本次末项为 9.2.21；未查询的其余标识不冒充不可用或已下架。Apple 返回的 releaseDate 在此样本中是应用首次发布日期，不作为各版本的发布时间展示。首次 QQ 试验未记录具体失败类别，不能事后确定原始原因；后续补充固定阶段/错误分类并规范化账号输入后复核成功。
