# 项目进展

更新于 2026-11-05。

目前已跑通 GitHub 上的原始 IPA 下载、模型恢复与复用、完整解密校验，以及 Telegram 私聊交付。机器人目前在 Debian 13 VPS 上常驻运行，只供管理员使用；多用户和收费还没接入。

## 当前实现

| 部分 | 当前实现 |
| --- | --- |
| Telegram | 最新版、指定旧版、按需加载的历史列表、任务查询、取消和文件取回 |
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

## 公共资源与历史列表加速

四个固定 Apple 公共资源使用精确路径和固定键缓存，每次恢复后仍检查长度和 SHA-256。缓存保存发生在读取账号凭据之前，不包含账号会话、授权模型、IPA 或整个用户目录。

[冷缓存准备 41951203095](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41951203095) 和 [另一平台恢复 41951409995](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41951409995) 均成功。后一次恢复约 5 秒、校验约 1 秒；此前重新准备资源的样本为 24–71 秒。

历史列表改为每批最多核对 10 个标识，以排他游标加载更早版本，单个应用最多展示 200 项。缓存扩大为 50 个应用，24 小时内直接使用，未满 7 天的旧缓存先显示并在空闲时刷新。已加载页面的翻页不启动 GitHub；按钮有效期仍为 6 小时。远程查询仍受每滚动 24 小时 20 次限制，包含首屏、刷新和加载更早版本。

[构建 41952137194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952137194) 的两个 macOS 平台各通过 424 项 Python 测试（各跳过 2 项）、11 项所选 Swift 测试及 Go 检查。[服务器构建 41952137779](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952137779) 在 Ubuntu 和 Debian 13 各通过 424 项 Python 测试（各跳过 1 项）。

实测 QQ 历史目录仍返回 335 个标识：

| 查询 | 结果 | 工作流作业耗时 |
| --- | --- | --- |
| [首批 41952989754](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41952989754) | 10 项，从 9.3.80 到 9.3.35；元数据步骤约 102 秒 | 2 分 22 秒 |
| [下一批 41953354529](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41953354529) | 另 10 项，从 9.3.30 到 9.2.85；元数据步骤约 41 秒 | 1 分 2 秒 |

两批标识不重叠，第二批从首批返回的排他游标继续。旧目录样本 [41941095718](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41941095718) 用时 8 分 32 秒、返回 33 项；新首屏返回项数更少，因此这是“更早看到可选列表”的对比，不是同等完整目录吞吐量的对比。以上不包含 Telegram 展示延迟，Apple 响应波动仍明显。

[My BVF 导出 41953586939](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41953586939) 作业总计约 59 秒：运行包 7 秒、资源恢复及校验 8 秒、完整导出步骤 27 秒；22 个加密切片、704 页校验通过，明文大小 10,251,249 字节。此前预编译版同应用样本约 1 分 49 秒。本次只核实 GitHub 加密导出，没有把 Telegram 发送或安装计入验证。

## 历史查询连接复用

历史目录的一批查询和指定显示版本号的搜索，现在各自复用一个禁止重定向的 HTTP 连接池，并只获取一次经过白名单校验的公开下载端点。连接池只存活于本次搜索，结束时关闭；版本请求仍然串行执行，每次重新生成签名，并使用当前账号令牌和 Cookie。元数据解析、版本绑定、时间预算和连续失败上限保持不变。

日志只记录公共配置请求、连接池和签名请求的数量，不记录端点响应、账号数据或签名内容。[QQ 首批实测 41956106639](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956106639) 确认有 2 次公开配置请求、1 个查询连接池和 11 次签名请求。标识发现仍单独请求 Apple；10 个版本逐一请求，签名没有被复用。

同一首批 10 个版本的标识、显示版本和下一页游标均与上轮一致。本次工作流作业约 55 秒，元数据步骤约 36 秒；上轮分别为 2 分 22 秒和 102 秒。[下一批 41956309828](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956309828) 同样返回原来的另外 10 项，游标保持一致；工作流作业约 1 分 3 秒，元数据约 50 秒，上轮则为 1 分 2 秒和 41 秒。因此重复准备开销确实减少，但两组样本并不能支持“所有查询都按固定比例提速”。

[构建 41954739130](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41954739130) 的两个 macOS 平台均通过 424 项 Python 测试（各跳过 2 项）、11 项所选 Swift 测试及 Go 检查，并完成成品包搬移后的启动验证。这轮只更新 GitHub 原生运行包，无需重启 VPS；后续任务自动获取匹配的已验证运行包。

[指定旧版导出 41956478397](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41956478397) 使用 App 1448246447、Apple 版本标识 830508655，约 49 秒完成 GitHub 作业；5 个加密切片、820 页通过校验，明文 8,436,045 字节。验证范围是指定版本绑定和完整加密导出，本轮没有重新发送 Telegram 文件或验证安装运行。

## 服务器与容量

在 [41953590065](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41953590065) 部署了按需历史列表和扩展缓存，运行代码提交为 `631fa149eac1b95d8c2dd9bc787541152a3e8ee4`。Ubuntu 和 Debian 13 各通过 424 项 Python 测试（各跳过 1 项），以及 Go、systemd 和部署健康检查。服务器只安装经过 GitHub 验证的成品，没有在服务器编译或执行测试。

IPA 审计采用分块临时文件和只读映射，避免把大程序整体读进内存。2,000,000,000 字节的加密、解密和摘要比对，以及超出 1 字节的拒绝行为，已在 [41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129) 用合成数据验证；尚未把 2000 MB 的真实游戏交付计为已验证。

服务器保留 current 和 previous 两版程序。正常传输结束会删除临时文件，异常残留在下次启动时清理；数据库和恢复备份保留。发送结果不明的任务不会在重启后自动重发。

## 接下来要做的事

- 补齐重签名、安装和实际运行测试，目前 `runtime_verified=false`。
- 扩大应用和账号样本，验证更多历史版本及接近容量上限的真实文件。
- 完成多用户、计费和正式运营所需的管理功能。
- 完善异地备份；现有数据库备份仍在同一台服务器。
- 继续锁定和审查传递依赖。现有包有构建来源与摘要，但不等于已经实现可复现构建。

早期原生接口失败、认证排查和模型恢复过程，保留在 [OFFLINE-BACKEND.md](../OFFLINE-BACKEND.md)、[原始下载记录](../NATIVE-DOWNLOAD-RESULTS.md) 和 [研究记录](RESEARCH.md)。旧版本文档可从 Git 历史查看。
