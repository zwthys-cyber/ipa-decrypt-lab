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
