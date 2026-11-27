# 中国区账号与链接识别

> 文档范围更新（2026-11-27）：本页在main保留旧代码/研究/发行历史。当前生产处理源码来自upgrade/managed-runtime-v0.2，已切换Cloudflare/D1 + CircleCI ARM64 + 私有Drive；main仍用于账号维护和旧Intel发行。[当前同名文档](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/CHINA-ACCOUNT.md) · [运行手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md) · [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。不要按历史VPS说明重启旧poller或重新启用5个退休派发工作流。

中国区独立模型已恢复，在新的 Intel 运行器复用及真实导出通过，链接路由已部署。机器人按 App Store 链接选择账号：中国区链接使用独立中国区账号，其余地区链接和数字 App ID 使用原外区账号。中国区支持免费应用最新版及可获取的历史版本，IPA 上限 2000 MB；原外区行为保留。

## 当前限制：国区专属应用的地区许可响应

2026-11-09 的真实国区任务 [42566676227](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566676227) 对抖音 `1142110895` 完成国区元数据检查、匹配运行包加载、保存模型/检查点验证和 Cookie 登录刷新，但在申请免费许可证时失败；没有下载或解密到应用。用户确认同一国区账号在 App Store 可以正常下载该应用。

[脱敏原生响应对照 42569885848](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42569885848) 在私有输入前查询的运行器出口国家为 **US**。免费许可接口返回 HTTP 200 字典，但没有正常购买成功标记；购买与直接授权下载两条路径的 Apple 提示均被固定词表归类为 `storefront/unavailable`，并出现提示对话框。没有验证码、令牌过期或原生 StoreAMD 失败证据。仅有 HTTP 200 不代表业务授权成功。

这些结果符合境外出口导致地区限制的现象，但没有完成“同一客户端、同一账号、仅改变为中国大陆出口”的对照，**尚不能把原因确定为 IP，也尚未修复抖音下载**。仍需区分 Apple 对运行环境的限制与客户端地区上下文兼容；没有配置可用的大陆代理/出口 Secret。下一步需要管理员提供可信大陆出口，正常 Apple TLS、目标主机限制和账号隔离继续保留。外区线路保持原样。

对照中跳过重复购买、直接请求既有授权的路径同样未返回有效安装包，不能据此上线“忽略许可”的改动。没有放宽响应、应用/版本、签名或明文验证，没有生成或发送该应用文件。中国区路由和两个已验证样本的模型证明仍有效，不能推广成全部中国区应用都可下载。

`cn-download-diagnostic.yml` 默认为无账号 `preflight`；诊断客户端只在 GitHub 编译、测试后使用，不替换普通运行包，不保存到生产 Swift 缓存。公开材料仅为关闭字段集合中的数字、布尔值和语义类别，原生消息、对话框文字、Cookie 和网络地址不公开。旧诊断中的 `native_license_failed/native_version_resolution_failed` 可能被诊断标记词触发；[分类隔离修正](https://github.com/zwthys-cyber/ipa-decrypt-lab/commit/b8790b7fc8035ab83a4fc13886af881bd7d91c22) 已排除这些标记，分析应优先使用真实阶段、结构和地区类别，不能据旧标签断言版本错误。

## 链接规则

| 输入 | 账号与行为 |
| --- | --- |
| `https://apps.apple.com/cn/app/名称/id1530340312` | 中国区最新版 |
| `https://apps.apple.com/us/app/名称/id333903271` | 原外区账号 |
| `https://apps.apple.com/de/app/名称/id333903271` | 原外区账号 |
| 纯数字 App ID 或没有地区的 Apple 链接 | 保持原外区默认 |
| `/versions 国区链接` | 使用国区保存会话查询最近10个历史版本，可分页、加载更早版本并点选 |
| `/version 国区链接 版本号或历史ID` | 固定国区账号下载指定版本，无法获取或版本不符则停止 |

识别的是链接里的地区，并不推断应用只在哪个国家上架。同一个 App ID 可以同时在多个地区上架；没有链接地区时不猜测账号。外区仍沿用原美区公开元数据预检，并非任意国家账号选择。只接受受信任的 HTTPS App Store 链接，不跟随第三方短链接或跨区失败回退。

任务编号绑定账号：中国区使用 `cn_` 加 32 位随机摘要，旧外区编号保持兼容。地区随任务保存在私有 SQLite 中，重启恢复、取消、进度、取回与回执校验均按同一账号工作。进度卡显示下载地区。白名单、用户隔离、串行准入和每日额度仍统一计算。

## 保存模型、状态与会话

普通国区任务通过固定 `china-private-delivery.yml` 在 GitHub macOS 26 Intel 上运行，只读取专用 CN Secrets：

- `APPLE_CN_ID`、`APPLE_CN_GUID`、`APPLE_CN_SESSION_B64`。
- `FAIRPLAY_CN_MODEL_B64`、`FAIRPLAY_CN_STATE_B64`。

任务核对保存检查点与 GUID，恢复私有会话缓存，执行一次非交互 Cookie 刷新后下载。它不挂载德国区材料或密码 Secret，不预填验证码，不初始化新模型、不申请新电脑授权。下载后复用国区模型，经过完整切片/页面、账号元数据清理、ZIP CRC 和应用身份验证，再加密为短期交付产物。公开附件只有 age 密文与脱敏回执，Apple 材料不进入 VPS。

Cookie 可能过期。需要验证码时普通任务明确停止，提示管理员维护中国区会话；不向下载用户索要账号验证码，不切换德国区账号。管理员维护仍使用专用认证与实时中继工作流，不保证永久免验证码。

`CN_RECOVERY_BACKUP_B64` 保留先前 Intel 检查点、GUID 和会话。新的 ARM 配置已晋升为主配置，旧备份与当前主配置不相等是预期结果；不得运行旧配置的相等核验后误判主配置，也不得覆盖旧备份。用户批准的一次额外电脑授权已经用完，最后观测数量为 **3/5**，没有授权第四台或全账号撤销。

## 最新真实证据

| 阶段 | GitHub 运行 | 结果 |
| --- | --- | --- |
| 获准的一次 ARM 初始化 | [42562058217](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42562058217) | 中国区 LocalSend 1661733229，31 个加密切片、11,744 页，模型恢复和独立完整明文校验均通过；授权数 2 → 3 |
| 同一会话实时验证码 | [42562413900](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42562413900) | 密文中继成功，临时验证码与一次性批准 Secrets 已删除 |
| 新 Intel 运行器复用保存模型 | [42563127722](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563127722) | 另一款国区样本 1530340312，6 个切片、164 页完整验证，检查点/GUID 匹配，不恢复模型、不新增授权、无验证码 |
| 保存状态独立重放 | [42563352128](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42563352128) | 同一小样本 6 个切片、164 页完整验证，状态绑定正确，数量仍为 3；最新会话已核验保存 |
| 链接、账号与恢复契约 | [42564779892](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42564779892) | 480 项主 Python、68 项隔离 Python、5 项 Node；覆盖国区链接、外区兼容、拒绝历史跨区、SQLite 恢复、用户隔离及公开进度的凭据隔离 |

[真实导出 42565938868](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42565938868) 使用保存模型完成另一款国区样本的 6 切片、164 页验证、账号清理与 age 加密；独立核验 ZIP/密文摘要及地区回执。链接路由已在 [42566050391](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566050391) 部署并返回服务 ready；[alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5) 已发布。没有新增 Telegram 测试文件发送，也没有验证一次真实用户的国区请求到收件全过程。

这些证据没有验证安装、重签名或应用实际运行。模型证明和机器人导出/部署是不同阶段；后者以 [项目状态](PROJECT-STATUS.md) 的正式导出、部署记录为准，没有额外向 Telegram 用户发送测试文件。

## 实时验证码维护

凭据入口是 [GitHub Actions Secrets](https://github.com/zwthys-cyber/ipa-decrypt-lab/settings/secrets/actions)。不要把验证码填进工作流公开输入。

先启动 `china-account-auth.yml` 的 `authenticate`，保持同一个原生 Authenticator 进程等待。只有可信的活动任务发出绑定运行、源码、随机标识和有效期的等待请求后，才获取新验证码。临时写入 `APPLE_CN_2FA_CODE`，由 `china-otp-relay.yml` 密文中继，并在中继后删除。超时或会话终止后停止，不能把旧验证码送进新的冷登录。原德国区账号拒绝安全升级的设置保持原样。

成功返回的会话必须匹配国区账号、稳定 GUID 和 storefront `143465`。原始客户端输出、邮箱、令牌、验证码、密钥和状态不进入日志或公开附件。候选材料只用仓库 Secrets 公钥密封；核实可信任务、源码、ZIP 摘要、文件清单、固定目的地和当前公钥后才写入对应 CN Secret。

## 历史故障与操作边界

- [42552374488](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42552374488)：首次授权 0 → 1，检查点因临时目录前缀不匹配而未保存。运行器已结束，不能声称可恢复；这一个名额仍占用。前缀和实际 sudo 保存契约已修复。
- [42554044136](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42554044136)：第二次授权 1 → 2，旧 Intel 检查点已保存，但两个样本均未通过 SINF 类密钥验证。这个配置保留在旧备份中。
- [42556247417](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42556247417)：诊断确认数据库认证和唯一记录匹配通过，许可证首块失败。未尝试其他密钥/记录或忽略校验。
- [42560593505](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42560593505)：发现 ARM/Intel 默认地区上下文为美区；显式国区上下文保持正文、设备标识和签名头正确。
- [42560812625](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42560812625)：旧配置在 ARM 重放仍失败，数量保持 2，无新增授权。不能把迁移 CPU 本身说成解决方案。
- 随后用户明确批准一次额外 ARM 初始化，恢复成功。初始化平台与地区上下文同时改变，不能断言某一项单独解释成功。旧回执中与旧 Intel 状态的 GUID 比较不代表新 ARM 配置绑定失败；新状态在保存与独立复用时均已核验。
- 授权数量摘要的 HTTP 500 通过只读查询使用 Configurator/2.17 解决；登录和下载继续使用已验证的 2.21 标识。这不意味着密码错误或整个账号失效。

已有可用模型和状态后使用保存模型或显式重放，不重复初始化。所有构建、测试与私有验证只在 GitHub-hosted Actions 上进行；VPS 只运行已验证的控制器成品。

## 国区历史版本实际验证（2026-11-10）

使用国区完整链接执行 `/versions` 可查询首批10条、翻页及继续加载更早版本；`/version 国区链接 版本号或历史ID` 固定使用国区保存会话。目录缓存按账号区分，按钮点选、刷新、重启恢复和下载收据均保留国区身份。最大展示200条，版本查不到或不匹配时停止，不回退最新版/外区；国区仍仅使用 macOS 26 Intel，不自动切换备用池。

[实际查询与旧版导出42726551974](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42726551974) 的 catalog、select、export 子作业均成功：LocalSend1661733229目录共32条，首批读取10条；选择严格旧于当前版本的1.18.1/历史ID889619746。31个加密镜像、11,716页通过完整明文证明，清理后26,887,278字节；仅保留一天期收件人密文，没有发送Telegram文件或安装运行验证。该运行最终汇总脚本漏传指纹根目录参数，因此整体为失败，不能标为全绿。

[只读证明修复42727462387](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42727462387) 校验原成功子作业、artifact摘要、账号/版本收据，并通过严格源码差异白名单确认导出及运行包源码未变，重建当前源码证明；没有再登录、下载或解密。早一轮修复误用仅允许Actions路径的客户端做源码比对，后改为单独只读Contents API，未扩大机器人API白名单。

[部署42727462163](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42727462163) 使用源码 `b70d0f3730651ebcc03c8d4ca31e9e5d4bd84c51`；默认双平台运行包42724891189、独立CN运行包42725944546、TF真实回归42726551778及国区旧版证明全部作为门禁。原CN/外区账号、GUID、保存模型和电脑授权保持不变。该样本不代表所有国区应用或旧版本均可取得，前文地区许可限制仍然适用。
