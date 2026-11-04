# 项目状态与使用说明

更新日期：2026-11-04。当前阶段：**GitHub-only 模型获取、真实 IPA 解密校验及跨运行器复用已完成验证**；真实 IPA 私有加密导出已验证，Telegram 限时私有交付已通过真实收发，跨会话恢复已通过合成验证；管理员常驻内测已部署到用户的 Debian 13 VPS，收费服务尚未开放。

## 已完成的三条路径

本轮固定测试 App ID 为 **6599842047**，三次运行均使用 GitHub-hosted macOS。

| 路径 | 实际结果 | 新增电脑授权 | 证据 |
| --- | --- | --- | --- |
| 首次恢复模型 | 下载原始 IPA、取得授权状态、恢复模型，再独立复核完整 IPA | 本次一次，数量 3 → 4 | [41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) |
| 直接复用模型 | 全新运行器读取模型 Secret，重新下载并验证 | 不调用电脑授权 | [41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) |
| 从检查点恢复模型 | 全新运行器读取保存的 SIDB/IOMAC 数据，重新恢复模型并验证 | 报告明确为 `authorization_request_attempted=false` | [41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765) |

三次均完成 **62 个加密切片、12,524 个页面**的明文校验，最终 `decryption_proven=true`、`plaintext_verified=true`。这些数量是本轮样本的记录，不是对其他应用或未来版本硬编码的通过门槛；实际校验要求覆盖审计器发现的全部加密切片，并核对可用的加密前页面哈希。

经验证的实现提交为 [b668df0](https://github.com/zwthys-cyber/ipa-decrypt-lab/commit/b668df099334706a9f02e6bcaf56ff553b023c8b)。后续状态整理为文档更新。

## 现在如何使用

### 常规解密验证：使用已保存模型

1. 打开 [Independent Swift Store trial](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/native-store.yml)。
2. 点击 **Run workflow**，分支选择 `main`。
3. 将 `decryption_backend` 明确选择为 **`offline`**，再执行。

该入口目前默认选择 `native`，其用途是原生诊断；常规模型验证需要手动选择 `offline`。现有手动工作流的测试目标是 App ID 6599842047。

通过标准是最终报告 `status=offline_plaintext_verified`、`decryption_proven=true`、`plaintext_verified=true`。单独的构建成功、Secret 编码检查成功或下载成功不代表解密校验成功。

### 需要重新恢复模型：使用授权检查点

打开 [Private same-runner model bootstrap](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/model-bootstrap.yml)，选择 `main` 和 **`mode=checkpoint-replay`**。

该模式从 `FAIRPLAY_STATE_B64` 恢复私有临时文件，并使用归档硬件标识完成模型推导，不向新主机的系统目录导入授权，也不调用机器授权。最终应为 `model_recovered_and_verified`，且两个明文校验标志均为 true。

该工作流各模式的含义：

| 模式 | 用途 | 账号操作 |
| --- | --- | --- |
| `preflight` | 构建、合成测试和环境检查；默认值 | 不使用 Apple 账号 |
| `input-inspection` | 下载并检查原始 IPA 的许可格式 | 使用现有账号下载，不调用机器授权 |
| `checkpoint-replay` | 从保存的状态重新恢复模型并验证 | 使用现有账号下载，不调用机器授权 |
| `trial` | 首次生成新的授权状态并恢复模型 | 会提交一次机器授权请求，可能占用名额 |

本仓库已有可复用模型和检查点，日常验证使用 `offline`；重新推导模型使用 `checkpoint-replay`。无需为重复验证选择 `trial`。

## 已配置的私有数据

| Secret 名称 | 用途 |
| --- | --- |
| `APPLE_ID` | 已配置的下载账号 |
| `APPLE_PASSWORD` | 该账号的密码 |
| `FAIRPLAY_MODEL_B64` | 已通过完整 IPA 校验的模型 |
| `FAIRPLAY_STATE_B64` | 固定 SIDB/SIDS 文件和必要硬件标识，用于重放恢复 |

模型和状态 Secret 已于 2026-11-04 14:22:53 UTC 保存。文档不包含它们的值。

工作流仅输出使用仓库公钥封装的模型/状态密文，**不会自行写入或覆盖仓库 Secret**。本次保存由已授权的 GitHub API 操作完成。重放产生的新模型密文未覆盖已经验证可复用的模型 Secret。

最新直接测得的电脑授权数量为 **4/5**，来自首次成功恢复试验；这是记录值，不是实时查询。此前用户批准的全部解除授权只执行过一次（5 → 0），不会作为常规重试清理步骤。

## Telegram 交付与 macOS 26 升级

用户请求 cb7bc7f3d855680a4e5cf55548507d3a 对应 App ID 1530340312。原 ARM 运行因 hosted runner 容量不足未开始执行；[Intel 恢复运行 41869909475](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41869909475)验证 6 个加密切片、164 页。[Telegram 会话 41870902876](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41870902876)确认发送 2,035,796 字节，用户确认收到。

新交付默认使用 macOS 26 Intel，备用为 macOS 15 Intel。26 的无账号预检和 [真实下载解密样本 41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)已通过；同一模型在 26 上再次校验上述 6 个切片、164 页，精确命中已验证的 Swift 缓存后跳过重复构建。编译与测试分步限时，ARM/Intel、15/26 缓存互相隔离。

已增加 3 分钟队列切换尝试、最多两次逻辑运行、执行前安全取消核对，以及“阶段已就绪 + finalized 密文产物”的及时交付门槛。305 项 Python 测试（1 项环境跳过）及真实密文归档摘要探针通过。详见 [运行说明](TELEGRAM.md)。

## 历史跨会话恢复

[验证运行 41890117885](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41890117885)通过 323 项 Python 测试（1 项环境跳过）和两个独立运行器的合成恢复验证。新会话自动接回最近一天内已记录的未完成任务；已交付或发送结果不明确的任务不自动重发。记录写入失败时不提交、不发送。

以上为已退役的 Checks 有界恢复实现。当前使用私有 SQLite，仍仅管理员可用，尚未开放多用户或收费；见 [现行恢复规则](SESSION-RECOVERY.md)。

## 常驻 VPS 接入

用户已授权服务器运行 GitHub 验证通过的成品。[部署运行 41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076)验证 Ubuntu 与 Debian 13 两套环境下各 347 项 Python 测试（1 项环境跳过）、Go 认证加密测试、真实 systemd 凭据挂载，以及发布包 SSH 安装和服务健康状态。

服务器使用非 root systemd 服务、持久 SQLite 任务记录、Telegram 更新防重放、自动重启和开机自启；仅管理员可用，收费入口关闭。下载及 FairPlay 解密仍由 GitHub macOS 运行器执行。服务成功登录 Telegram、回读菜单并确认发送启动消息；尚未将这次迁移后的真实 IPA 新任务交付算作已验证。

旧限时轮询及身份查询入口、Checks 恢复实现已删除，防止误启动第二个轮询进程。代码、安装器、权限与回滚说明见 [VPS 部署文档](VPS-DEPLOYMENT.md)。

## 尚未完成的部分

- **IPA 交付**：真实私有加密导出已通过 [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867)，移除账号元数据后的文件为 92,118,013 字节；只保留一天 age 密文，明文仍不公开。[真实 Telegram 大文件交付 41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056) 已确认完整发送该 IPA，发送前在 Linux 完成私有解密、摘要及结构复核。
- **安装运行**：尚未验证重签名、安装和实际运行，`runtime_verified=false`。
- **扩大兼容范围**：更多应用、其他账号/版本及真实 Linux 平台解密尚未完成实测；已有 Linux 构建与合成测试不能代替这些证据。
- **独立签名信任验证**：页面哈希校验不等同于独立的 Apple CMS 信任验证。
- **产品与部署**：用户已恢复 TG 接入。管理员私聊 /id 与 92 MB 完整文件回传已完成真实收发；提交、查询、取消代码及 289 项 Python 测试（1 项跳过）已接入。启动方法见 [Telegram 私有交付测试](TELEGRAM.md)。管理员常驻内测已接入；多用户和计费服务尚未完成。

## 进一步阅读

- [仓库首页](../README.md)：结果概览和工作流目录。
- [完整研究记录](../OFFLINE-BACKEND.md)：各阶段成功与失败证据、固定依赖和验证边界。
- [下载接口实现](../ENT-DOWNLOAD.md)：原始 IPA 下载链路。
- [项目约束](../AGENTS.md)：仅 GitHub 执行、私有数据保护及用户设定。

## 旧文件清理（2026-11-04）

清理提交 `a5e78c27b25a6c10efea46f9a84d0211385db503` 已通过 [GitHub 发布验证 41900942436](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41900942436)：Ubuntu 与 Debian 13 各 341 项 Python 测试（1 项跳过），Go 与真实 systemd 凭据检查成功，发布包生成成功。本轮未重新部署，VPS 仍运行先前已验证版本 `06bcf81`。

- 删除三个已退役工作流：限时 Telegram 会话、云端身份引导、Checks 恢复实验。
- 删除旧身份引导脚本、限时会话 CLI、Checks 日志模块及专用测试文件。
- 将仍使用的控制器移至 `telegram_controller.py`，更新守护进程、发布文件列表和测试引用。
- 保留并迁移 9 项控制器恢复测试到真实临时 SQLite；移除 6 项旧 Checks 专属或已有 SQLite 覆盖的测试，因此总数从 347 调整为 341。
- 现行模型、下载、解密、交付、构建缓存工作流及研究证据继续保留。已删除代码可通过 Git 历史查阅，不另存过时代码副本。

## 历史：QQ（App ID 444934666）审计限制复核

任务 `4f99d3d815873a46c93a0ec3d500f552` 原运行 [41901560282](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41901560282)仅报告 private_export_failed，未保留足够错误分类，不能仅凭此认定账号或解密失败。

新增安全阶段与错误码后，[41904195598](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41904195598)确认下载后触发 4096 条归档条目限制。上限调整至 32768 后，[41905063840](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41905063840)触发单 Mach-O 128 MiB 限制；调整至 512 MiB、总读取预算 2 GiB 后，[41906323142](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41906323142)仍报告 macho_member_limit，failed_stage=auditing。应用查询、账号登录和原始下载均通过，但尚未进入解密，未生成可交付文件。

当前代码 `8c0d4f5a2746cc9f58af04209da2837d4d12ab45` 已由 [41906318760](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41906318760)构建、部署并通过服务健康检查，Ubuntu 和 Debian 13 各 347 项测试（1 项跳过）。QQ 支持仍未完成；后续应改为有界流式/磁盘映射审计，避免通过持续提高整文件内存读取上限适配大型应用。不应跳过结构、明文或摘要校验。

## QQ 流式审计与真实导出已通过（2026-11-04）

[真实运行 41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)成功处理 App ID 444934666：19 个加密切片、131440 页明文校验通过，清理后的 IPA 为 341766793 字节，状态 encrypted_artifact_ready，plaintext_verified=true。安装和实际运行仍未验证（runtime_verified=false）。

任务编号 `4f99d3d815873a46c93a0ec3d500f552` 保持不变。仅发布 age 密文与收据，产物 13361017588 在 2026-11-05 20:41:15 UTC 到期。原失败任务不因人工复核自动重发；管理员可在机器人私聊执行 `/get 4f99d3d815873a46c93a0ec3d500f552`。尚未把本次 Telegram 文件发送计为已确认。

审计器以 1 MiB 分块写入私有临时文件，再使用只读映射检查结构，FAT 切片使用视图而非整片复制。单 Mach-O 上限 1 GiB、总读取预算 2 GiB、归档条目 32768；IPA 总大小上限保持 1 GiB。完整成员 CRC、长度、路径、结构和明文校验保留，临时文件在正常与异常路径关闭删除。

[部署验证 41907700244](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907700244)在 Ubuntu 与 Debian 13 各通过 352 项测试（1 项跳过），包括真实构造的 513 MiB 合成成员及 Python 跟踪内存峰值小于 16 MiB 的断言。该断言不是整个服务 RSS 的测量。Go、systemd 凭据与部署健康检查通过，VPS 已运行提交 `25c4c657d452622db5ad9c6b08790a5a30f2b2df`。全部编译与测试在 GitHub 完成。

## 当前容量：2000 MB

用户将直传上限定为 **2,000,000,000 字节（十进制 2000 MB）**，不支持 4 GB IPA，不启用分卷或下载链接。官方本地 Bot API 支持上传至 2000 MB，见 [Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

容量由 `tools/capacity.py` 统一定义：IPA 与单 Mach-O 上限均为 2,000,000,000 字节，Mach-O 总读取预算 4,000,000,000 字节，归档展开预算 6,000,000,000 字节，条目上限 32768。密文及外层 ZIP 另留明确封装开销；发送前再次执行严格明文大小检查。支持上限内的文件不等于所有应用均兼容。

处理前要求至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。可用应用元数据已表明超限时，在登录/下载前拒绝；元数据缺失时，下载后仍按实际大小检查。生成完成后及时删除不再需要的私有中间文件。下载超时 20 分钟、解密 15 分钟、交付加解密 10 分钟、Telegram 上传 20 分钟；GitHub worker 整体限时 70 分钟。

超限与磁盘不足通过固定 Actions 步骤标记传给机器人，使用中文提示；不读取或公开原始账号日志。发送结果未知仍不自动重发。

[发布与部署 41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129)通过 Ubuntu 和 Debian 13 各 357 项 Python 测试（1 项跳过），以及恰好 2,000,000,000 字节的 age 加密→解密→完整 SHA-256 比对和超出 1 字节拒绝测试。该大文件是 GitHub 上的合成数据，不是 2000 MB 游戏解密或 Telegram 真实上传实测。Go、systemd 凭据挂载与部署健康检查均通过。部署代码为 `4f3f79600a8f5df74c71eef6d0c03168d2895e13`。

[macOS 26 Intel 预检 41910548494](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910548494)已成功完成。独立 CMake/审计入口修复后的 [41910809719](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910809719)中 Ubuntu 与 macOS 15 Intel 已通过；记录时 ARM 任务仍在排队，不计为已通过。

## 提交前检查与旧发布自动清理（2026-11-04）

机器人在创建任务、写入恢复记录和占用日额度之前，用无账号 App Store 查询核对美区上架、免费状态及标注大小。未通过会直接说明原因；网络错误不当成地区不匹配。查询使用 8 秒网络超时、2 MiB 响应预算，不自动重试、不跟随重定向。

手动触发 GitHub 导出也会在拉取外部源码和编译之前检查。[闲鱼 510909506 复核 41919666036](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41919666036)预期拒绝 app_not_found_in_us，查询约 0.58 秒，整个作业约 18 秒；全部依赖构建、账号访问和解密步骤跳过。正常机器人拒绝发生在 GitHub dispatch 之前，不需要等待运行器。尚不支持中国区账号下载。

[发布 41919936183](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41919936183)在 Ubuntu 与 Debian 13 各通过 371 项测试（1 项跳过）、2000 MB age 流式验证及 systemd 凭据验证，部署与健康检查成功。

`deploy/prune_releases.py` 在新服务健康确认后仅保留 current 和 previous 指向的版本；只删除 releases 下符合提交 SHA 命名的真实旧目录，不跟随符号链接，不接触数据库、凭据、传输或 Telegram 状态。重复部署同一版本保留原回滚目标。清理异常只报告延后，不把健康部署当成失败。

本次实际删除 6 个旧版本，服务器仅余 2 个发布目录，总计约 100 MiB。检查时传输临时目录约 4 KiB、Telegram 总状态约 44 KiB、系统 journal 约 8.1 MiB；没有发现遗留的大 IPA。状态为 ready，task_active=false。正常临时传输在结束时删除，异常残留在下一次启动清理，审计临时文件随关闭/进程退出释放。数据库和单份恢复备份保留；未配置额外的全系统日志清空操作。

## VPN Cat 交付中断复核与修复（2026-11-04）

任务 `b979e75c067a53fabb53f77f672e849c`（App ID 1134784923）的 [GitHub 导出 41926194180](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41926194180)成功：3 个加密切片、2784 页，明文大小 18,888,772 字节，plaintext_verified=true；安装运行未验证。

22:36:56 UTC，VPS 记录 persistent_service_failed 后以退出码 2 结束，约 20 秒后自动重启。该时段没有发现 OOM、磁盘不足或内核 I/O 错误，也不是部署引发的重启。旧日志未保存异常类型，无法还原最初触发异常的具体原因；不能把网络超时当作已证实根因。复核时，同一加密产物的下载、归档摘要、收据绑定及密文大小/摘要均通过，未再次解密或向 Telegram 发送。

已确认两处缺陷：交付准备阶段的未处理异常会传播到守护进程并使其退出；旧代码在下载产物前就写入 sending，重启后因此可能错误提示“上次发送结果需要确认”，该提示不能证明已开始上传。

修复后，下载与校验期间保持 pending，仅在即将上传时持久化 sending；交付异常在任务内处理，区分“尚未上传”和“发送结果未知”。产物 GET 传输失败最多尝试两次，不重试 Telegram 文件发送或任务提交。错误诊断仅记录固定阶段、分类和允许名单中的异常类型，不记录异常正文、凭据或签名下载地址。已处于历史 sending 状态的任务仍需管理员确认后使用 /get，不自动重发。

[发布与部署 41927868761](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41927868761)在 Ubuntu 和 Debian 13 各完成 378 项 Python 测试（1 项跳过），部署健康检查通过。线上版本为 `36be288c4315962d91d32ff38b1cc16dc8a29be1`；部署后检查 active/running，NRestarts=0。此记录不代表该历史任务已重新交付。

## 历史版本实时下载已接入（2026-11-04）

代码 `f897310bd0c92860ed2c27cb4001dce1da444398` 新增管理员私聊 `/version AppID或商店链接 版本号`，也可指定 Apple externalVersionID。使用现有账号和 Apple 历史元数据，不依赖第三方解密或历史 IPA 缓存。查询最多核对较新的 120 个历史标识，请求间检查 180 秒预算；明确区分查询/下载失败，不回退最新版。详细边界见 [Telegram 使用说明](TELEGRAM.md)。

[真实运行 41931938986](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41931938986)成功取得 QQ（444934666）9.3.55。下载响应绑定 Apple 版本标识，原始及清理后的 IPA 显示版本均通过精确核对；20 个加密切片、126580 页明文校验通过。IPA 为 324952532 字节，plaintext_verified=true，runtime_verified=false。公开产物仅包含 age 密文和非敏感收据，保留至 2026-11-05 23:20:34 UTC。任务编号 `935501a1a8d66e691dc2470d84f6eade` 可由管理员使用 /get 取回；本轮未确认 Telegram 实际发送。

该运行完成 386 项 Python 测试（1 项跳过）和 10 项所选 Swift 测试。[部署 41932870509](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41932870509)在 Ubuntu 与 Debian 13 各完成 386 项 Python 测试（1 项跳过）、2000 MB age 流式验证、真实 systemd 凭据挂载与服务健康检查，部署成功。VPS 菜单配置包含 version 指令。重启恢复及备用运行器保留版本绑定，VPS 在发送前再次核对收据和 IPA 实际版本。

第一版仍限美区免费应用、管理员私聊、2000 MB 实际 IPA；未开放 Bundle ID 输入、多用户或收费。一个旧版成功不代表所有历史版本都可取得，也不代表已验证安装运行。
