# 项目进展

更新于 2026-11-05。

目前已跑通 GitHub 上的原始 IPA 下载、模型恢复与复用、完整解密校验，以及 Telegram 私聊交付。机器人目前在 Debian 13 VPS 上常驻运行，只供管理员使用；多用户和收费还没接入。

## 当前实现

| 部分 | 当前实现 |
| --- | --- |
| Telegram | 最新版、指定旧版、可点击历史列表、任务查询、取消和文件取回 |
| 服务器 | Debian 13、非 root systemd 服务、私有 SQLite、异常重启、开机自启 |
| macOS 任务 | 默认 macOS 26 Intel，备用 macOS 15 Intel |
| 运行包 | 两个平台分别构建，普通任务直接获取约 28 MB 的成品包 |
| 应用范围 | 美区免费应用，账号必须具备下载许可 |
| 文件大小 | 最多 2,000,000,000 字节，不分卷 |
| 结果校验 | 加密切片、可用页面哈希、归档结构、摘要和版本绑定 |
| 交付 | GitHub 只保留一天 age 密文；VPS 校验后发到管理员私聊 |

日常入口见 [Telegram 说明](TELEGRAM.md)，部署操作见 [VPS 说明](VPS-DEPLOYMENT.md)，成品下载见 [Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases)。

## 模型恢复与复用

最初使用 App ID **6599842047** 做固定样本。下面三次都完成了 62 个加密切片、12,524 页的明文校验：

| 路径 | 记录 | 电脑授权 |
| --- | --- | --- |
| 首次恢复模型 | [41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) | 当次新增一次，观测数量从 3 到 4 |
| 在另一台运行器复用模型 | [41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) | 没有新增授权 |
| 从检查点重放 | [41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765) | 没有新增授权 |

这些数量来自样本，代码不会把它们当成固定通过条件。每个任务都要按实际 IPA 检查全部加密切片。

模型保存在 `FAIRPLAY_MODEL_B64`，SIDB/IOMAC 检查点保存在 `FAIRPLAY_STATE_B64`。两者都是私有 Secrets，不随源码或成品包发布。日常任务直接复用模型，不重新占用电脑授权名额。

需要手动验证时，可运行 `native-store.yml` 的 `offline` 模式；需要从现有检查点重新推导模型时，可运行 `model-bootstrap.yml` 的 `checkpoint-replay` 模式。初始 `trial` 会涉及机器授权，不用于日常重试。

最后一次实测的授权数量是 4/5，这是历史记录，不是实时查询。此前只做过一次全部解除授权，记录为 [41837099155](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41837099155)；后续没有把它当作清理或重试步骤。

## 下载与交付记录

| 内容 | 结果与记录 |
| --- | --- |
| 完整 IPA 加密导出 | [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867)：92,118,013 字节，62 切片、12,524 页通过 |
| Telegram 大文件交付 | [41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：取得 92,118,013 字节文件的发送回执 |
| macOS 26 实际样本 | [41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)：App 1530340312，6 切片、164 页 |
| QQ 流式审计和导出 | [41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)：19 切片、131,440 页，341,766,793 字节 |
| QQ 9.3.55 指定旧版 | [41931938986](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41931938986)：20 切片、126,580 页，324,952,532 字节 |
| 历史列表与按钮 | [41941057460](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941057460)：列出 App 6749145363 的 3 个版本；点击后产生的 [41941946764](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941946764) 已完成导出 |
| QQ 历史列表 | [41941095718](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941095718)：335 个标识，时间预算内查到 33 个版本 |

分别记录“工作流导出成功”和“Telegram 发送成功”，上表只有明确拿到发送回执的项目才算交付完成。安装和实际运行是另一项验证，目前还没完成。

## 预编译加速

重复的 Go 安装、原生编译、Swift 构建树恢复和测试套件，已移至 `native-runtime-build.yml`。它在源码变动时构建两个 Intel 平台的运行包，普通下载和目录查询只取成品。

包内包含四个程序、必要的公开 Swift 资源和许可证。清单记录源码指纹、系统平台、生产提交、运行编号及逐文件 SHA-256。消费端只接受成功的 main 分支构建，下载后再次校验，不使用不匹配的旧包。

| 验证 | 结果 |
| --- | --- |
| [构建 41946086966](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41946086966) | 两个平台均通过 414 项 Python 测试（各跳过 2 项）、10 项所选 Swift 测试和 Go 检查；原构建目录移走后启动正常 |
| [全新机器 41947134774](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947134774) | 两个平台获取并校验运行包约 3–4 秒 |
| [My BVF 41947479965](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947479965) | 包准备 8 秒，公共资源准备 24 秒，导出处理约 42 秒；总计约 1 分 49 秒 |
| [历史查询 41947789366](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41947789366) | 包准备 4 秒；总计约 1 分 43 秒，得到全部 3 个返回版本 |

My BVF 之前的 [41935307617](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41935307617) 用了约 4 分 2 秒，两次样本相差约 55%。这不是固定速度承诺，也没有把 Telegram 上传时间计入这次对比。

Actions 运行包保留 30 天，每周重建一次。改动 tools/、tests/ 或构建工作流后，要先等新包构建成功。缺包或过期时任务会在读取 Apple 凭据前停止；手动运行构建流程即可补包。公开 Release 是版本快照，普通任务目前仍从 Actions 获取匹配包。

## 服务器与容量

在 [41940545752](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41940545752) 部署了带历史列表的服务器版本，Ubuntu 和 Debian 13 各通过 407 项 Python 测试（1 项跳过），以及 Go、systemd 和健康检查。后续预编译升级只改 GitHub 工作流，没有重启服务器。

IPA 审计采用分块临时文件和只读映射，避免把大程序整体读进内存。2,000,000,000 字节的加密、解密和摘要比对，以及超出 1 字节的拒绝行为，已在 [41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129) 用合成数据验证；尚未把 2000 MB 的真实游戏交付计为已验证。

服务器保留 current 和 previous 两版程序。正常传输结束会删除临时文件，异常残留在下次启动时清理；数据库和恢复备份保留。发送结果不明的任务不会在重启后自动重发。

## 接下来要做的事

- 补齐重签名、安装和实际运行测试，目前 `runtime_verified=false`。
- 扩大应用和账号样本，验证更多历史版本及接近容量上限的真实文件。
- 完成多用户、计费和正式运营所需的管理功能。
- 完善异地备份；现有数据库备份仍在同一台服务器。
- 继续锁定和审查传递依赖。现有包有构建来源与摘要，但不等于已经实现可复现构建。

早期原生接口失败、认证排查和模型恢复过程，保留在 [OFFLINE-BACKEND.md](../OFFLINE-BACKEND.md)、[原始下载记录](../NATIVE-DOWNLOAD-RESULTS.md) 和 [研究记录](RESEARCH.md)。旧版本文档可从 Git 历史查看。
