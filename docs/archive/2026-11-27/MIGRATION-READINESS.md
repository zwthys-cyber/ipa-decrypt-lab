> 历史资料归档 · 2026-11-27
>
> 本文保留归档时的实验、判断与验证记录。日常使用见[使用指南](../../TELEGRAM.md)，当前范围见[项目状态](../../PROJECT-STATUS.md)。[原始来源](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/977b239ee2e35c908361109c8d0e10d1fa252873/docs/MIGRATION-READINESS.md)。

# v0.2 生产迁移：运行环境与接受历史

截至2026-11-27，生产已切换到原机器人 + Cloudflare Workers/D1 + 按需CircleCI macOS ARM64 + 私有Drive交付。[成功切换45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266)对应处理源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`。CircleCI75真实国区任务已完成下载、17镜像/120,976页严格验证、342,632,968字节私有上传及主人通知；新平台历史版本交付和新TF任务仍待分别真实验收。

生产已采用不可用旧机的离线交接路径，已验证原bot新Token、旧Token拒绝、5个旧工作流停用、29任务/89updates/14metadata读回和新源码cron。TF历史确认tombstone已封存，未重新接受；2条旧pending和源缺口保持held，未取得旧机物理停机证明。

新的完整验收仍包括历史版本交付和新TF任务；已恢复历史去重与接入代码不等于这些新任务实测完成。操作见[运行手册](../../OPERATIONS.md)。费用策略不自动开通付费/超额；下表是2026-11-26的历史平台调查，不是当前价格保证或部署建议。

## 2026-11-26：历史平台调查

保留无人值守、纯云端、零订阅及超额费用、无需主人维护电脑或 VM，以及私有链接最多 10 GB 的既定约束。控制器、Apple 原生处理和大文件校验/上传是不同的能力；一种免费服务支持其中一项，不能证明完整链路可运行。

| 候选 | 本轮复核的官方事实 | 当前判定 |
| --- | --- | --- |
| Cloudflare Workers Free | 100,000 请求/天、每个 HTTP 请求 10 ms CPU、128 MB 内存。[资源限制](https://developers.cloudflare.com/workers/platform/limits/) | 继续作为已有试验控制面的候选，不能运行现有原生控制器/处理程序。 |
| Cloudflare Containers | 需要每月 5 美元 Workers Paid，并按量计费。[定价](https://developers.cloudflare.com/containers/platform/pricing/) | 不符合零费用约束。 |
| Fly.io 新 Free plan | 11 月 23 日新增每月 5 美元额度；用尽后转为 Pay As You Go，工作负载继续运行。[官方变更](https://fly.io/changelog/introducing-the-free-plan/) | 不构成零费用硬上限，不注册或部署。 |
| Koyeb Free | 512 MB 内存、2 GB 磁盘，不支持 Worker Services 或持久卷；官方建议不用于生产。[实例限制](https://www.koyeb.com/docs/reference/instances) | 不满足现有控制器及持久状态要求。 |
| Northflank Sandbox | 定价页宣传免费、无卡；部署文档仍要求支付方式，并明确 Sandbox 不用于生产。[定价](https://northflank.com/pricing) · [部署计费说明](https://northflank.com/docs/v1/application/billing/pricing-on-northflank) | 官方材料存在差异，不能把营销页当作生产及零收费批准。 |
| Hugging Face Spaces | CPU Basic 无小时费，但创建 Docker/Gradio 计算 Space 需要付费计划。[官方说明](https://huggingface.co/docs/hub/spaces-overview) | 不符合当前要求。 |
| Modal Starter | 有净支出上限功能；本文没有验证本账号所有计费项目的零美元设置。默认执行环境为 Debian Linux。[支出上限](https://modal.com/docs/guide/budgets) · [运行镜像](https://modal.com/docs/guide/images) | 不能部署现有已验证的 macOS 处理链路，也未完成账号零收费验证。 |
| Scaleway Apple silicon | M4 价格为每小时 0.22 欧元。[定价](https://www.scaleway.com/en/pricing/apple-silicon/) | 可以提供 Apple 硬件，但需要费用。 |
| OCI Always Free A1 | 是 Linux ARM VM，并非 macOS 服务。[官方资源](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) | 不符合不让主人维护 VM 的既定要求，也不能直接替代当前 Apple 原生处理。 |

在2026-11-26该轮调查结束时，没有**已验证满足全部条件**的生产目标。这不等于证明市场上不存在任何可能方案。不能通过开通付费服务、默认升级、循环调用 CI 或让主人手机/电脑充当运行器来消除缺口。该检查点的GitHub Actions与CircleCI尚只用于开发验证；之后的主人授权按需处理与生产切换见本文开头。

现有离线 Go 解密引擎已有 Linux 合成检查，但这不等于已验证全部 App Store/TestFlight 账号、下载与实际明文处理可以迁至 Linux。完整迁移需要目标平台上的授权集成证据；不把归档校验、镜像导入或模型格式检查当作真实原生处理成功。

## TestFlight 接受历史的证据链

### 已直接读回的历史证据

| 证据 | 已核实内容 | 解释边界 |
| --- | --- | --- |
| [原接受作业 42692803345](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42692803345) | 闭合收据为 `acceptance_attempted=true`、`post_response_confirmed=true`，最终 `acceptance_outcome_unverified`。 | 原作业失败，不能写成成功；接受响应不单独证明成员资格。 |
| [后续只读确认 42694923538](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42694923538) | `membership_verified`、`invitation_accepted=true`、`acceptance_attempted=false`。 | 确认了原邀请的成员资格，没有重复接受。 |
| [持久会话推广 42703942768](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42703942768) | 闭合收据为 `ciphertext_persisted`。 | 需要另行将当前源密文与当时摘要绑定，不能只看文件存在。 |
| [生产请求 42714371079](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714371079) | `acceptance_attempted=false`、`invitation_accepted=true`，完成加密导出。 | 这一次请求不会触发接受记录库的惰性初始化。 |

原 [durable intent](../../../.github/ops/tf_invite_intents/298ad9a0bb3e8e78ebccad99f91c2f7273608575e54f35191206fc2a3fde9019.json) 与首次记录提交 `4ab1590d3a87d7ce45b853c297346fef8f0c06c2` 的 Git blob 同为 `7e233cd2eab2009b961bf8718ebf822fe6a6dc7f`。不删除、覆盖或重新激活它。

本轮列出了虚拟 TF 工作流的 59 次保留运行，并逐一读取最新 attempt 的任务步骤元数据；只有 42692803345 出现接受意图及接受步骤。正式 TF 交付工作流的保留运行列表只有上述一次请求。另从五次真实执行的导出 smoke 日志中读回了 `acceptance_attempted=false` 的闭合结果（42708565855、42711827732、42712411043、42716962584、42726551778）。部分 smoke 工作流只有公共测试执行；不能把整条工作流的 success 当作实际导出成功。

这些是 GitHub 当前保留的记录，不证明已删除运行、仓库外操作或所有历史状态不存在。缺少数据库的现象与接受逻辑尚未初始化相符；不能由此直接创建空库并宣布迁移完整。

### 只读源审计

`tf-ledger-source-audit.yml` 在 GitHub 先执行合成测试，再通过原有 Secrets 和严格 SSH 主机指纹校验，将标准库审计脚本传入 VPS 的 Python stdin。不会安装或执行测试套件，不安装脚本，不调用状态 helper，不调用 Apple 或 Telegram，不修改/创建/推广任何记录库。

审计使用 SQLite `mode=ro`、`query_only=ON` 和只读事务，包含 WAL 中的已提交行；只输出固定状态、布尔值和计数。它检查：

- 当前心跳是否新鲜、是否观察到 ready 且无活动任务；心跳不满足时仍可报告只读库存，但不能据此授权冻结或切换。
- TF 任务计数及未完成数量，不公开请求、用户、账号或邀请标识。
- 当前会话密文是否匹配原 CI 推广摘要，只输出匹配布尔值，不解开会话。
- 标准接受记录库及有限目录内旧候选文件是否存在；现有库中未解决结果的计数。
- 原私有发送回执库中的确认与未知发送记录，绝不重新发送。

本审计对不同数据库分别观察，不是跨库一致快照，也不是迁移通过证明。重建或迁移前仍须在批准的空闲切换窗口冻结全部写入、保存一致加密备份，并核对源任务与历史证据，保留所有未知结果及原发送回执库。当前缺失记录库时不能使用初始化 helper 制造来源证明。

### 2026-11-26 实时观察结果

[只读源审计 45811165425](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45811165425) 成功，源码为 `6d9e4c950ec583ef0d863dd7ef39355df3a5ba39`。8 项公共合成测试先通过，随后 Intel macOS 运行器经 IPv4 和固定主机指纹读取源状态。Linux 运行器此前发生连接超时；不能据此认定 VPS 不可连接。

源心跳新鲜且当时为空闲；TF 任务共 1 条、未完成 0 条；会话密文与原推广摘要匹配。标准接受记录库不存在，有限扫描范围内的候选库为 0。私有发送回执共 1 条、未知发送为 0。缺库时报告的未解决接受行数为 0，只表示没有行可读，不能证明历史上绝无未知接受结果。

这些实时观察与已验证的历史日志一致，提供了恢复已知历史成员记录的依据。没有停止服务、创建数据库或重新接受邀请。

### 带来源证明的恢复候选

`tf-history-recovery.yml` 先在 GitHub 运行合成测试，才允许执行受标记控制的候选构建。构建器重新读取固定源审计、原接受/后续确认/生产任务的元数据和闭合日志；分别保持原接受作业失败、只读确认成功的事实。新的生产或虚拟 TF 运行历史、源审计中的额外记录或未知结果、密文不匹配，都会阻止构建。

它校验固定 Git blob 的原加密意图包，并只在 GitHub 私有临时目录用既有交付密钥验证内层来源。过期意图只作为历史证据，不重新成为接受许可。候选库包含原 helper 的已确认历史记录和额外的来源表，不包含 Apple 会话、模型、生产任务库或发送回执库。

最终只允许保留 `acceptance.sqlite.age`、闭合收据及校验和，保留一天。收据明确 `production_installed=false`、`source_modified=false`、`requires_fresh_source_audit=true`。此候选补齐已知历史的可验证恢复路径，不能替代全量一致备份，也没有改变当前 VPS。安装前必须重新核对源变化及完整历史；有现存或新增接受记录时不得覆盖它们。

[恢复作业 45812495918](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45812495918) 在源码 `00dca9f9fb3ddb7815644fec51282d2c3fcf74ef` 成功：6 项公共测试通过，真实历史日志、意图包解密及来源绑定通过，单条历史记录候选加密后解密回读一致。收据为 `encrypted_candidate_ready`，明确没有 Apple 请求、源修改或生产安装。

产物：`tf-history-recovery-45812495918`，artifact ID `15114346825`；ZIP SHA-256 `1b8d243d12e464ebb8f18d78a8c021cbe2ac8fbd5ed31fa03ed063c57df9fc4f`；内层候选密文 SHA-256 `0c3e3367e85ce948806b0f8299bd4c3164b7a680b4d17317578699fea2a99842`。上传后的 artifact 元数据已读回，产物保留一天。过期后不能假定仍可下载；再次构建也不免除安装前的全量源核对。

截至2026-11-26该检查点：已验证历史接受来源并产出加密恢复候选，当时尚未完成生产安装。2026-11-27已通过离线交接及历史tombstone封存完成切换，证据见本文开头；原失败作业仍按失败保留。
