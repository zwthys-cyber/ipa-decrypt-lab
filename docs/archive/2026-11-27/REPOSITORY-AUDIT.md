> 历史资料归档 · 2026-11-27
>
> 本文保留归档时的实验、判断与验证记录。日常使用见[使用指南](../../TELEGRAM.md)，当前范围见[项目状态](../../PROJECT-STATUS.md)。[原始来源](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/977b239ee2e35c908361109c8d0e10d1fa252873/docs/REPOSITORY-AUDIT.md)。

# 仓库与文档审计

核对日期：2026-11-27。检查基线为生产源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`，不是维护文档提交的上线证明。生产、维护、默认main三个分支的职责仍分开；本轮不合并main代码，不推进开启中的生产HEAD，不执行Apple/上传/通知任务。

## 检查范围与结果

| 项目 | 结果 |
| --- | --- |
| 生产树 | 548个受控文件；完整目录清单未截断 |
| 文本 | 读取547份公开源码/配置/文档；原TF意图JSON仅核对路径/引用和Git元信息，不公开读取其中状态内容 |
| Markdown | 原有27份，全部检查相对文件链接；原始断链0处 |
| 完全重复 | 按Git blob比较，0组完全相同文件 |
| 误提交产物 | 未见IPA、ZIP/tar/gz、age密文、SQLite/DB、pyc、node_modules、__pycache__或.DS_Store |
| 工作流 | 当前树87份；GitHub登记95份，8份仅剩历史登记 |
| main差异 | main有388个文件/25份Markdown；不是当前机器人处理源码，不能直接以清理为由覆盖 |
| 显式源码路径 | 检查工作流/源码中的固定项目路径；仅3处测试中临时生成的合成路径，不是缺失运行文件 |
| 原生来源 | 文档整理不改tools/tests/.github/ops及原生构建合约，不触发原生重编译 |

静态引用检查不能证明没有动态入口、外部脚本或手工调用；不把“没搜到文件名”作为充分删除依据。未读取Secrets、私有链接、原生账号缓存或第三方IPA。

## 已发现并修订的过时说明

- README、索引及多份指南仍称VPS为现网、v0.2未上线：改为Cloudflare/D1 + CircleCI ARM64 + 私有Drive，补齐切换45918215266及真实国区75证据。
- 当前生产、维护和main分支职责混在一起：明确生产HEAD绑定、维护发布顺序；main保留账号/Intel发行维护用途。
- Telegram文档仍列旧/latest、/decrypt、/id、/allow、/deny、/users及无编号/cancel：新指令表只列实际实现，说明主人限制、pilot_任务号及Drive链接交付。
- 旧五秒计时卡、多用户、BotAPI附件、全服务20次等直接当作新能力：更正为当前实现；额度由配置控制，未设默认3次，目录查询单列限制。
- 将旧历史/TF成功自动算作新平台验收：明确已接入与CI验证、旧平台实测、新平台实测三者范围。历史版本完整交付、新TF请求仍待各自验收。
- 将通用会话错误或摘要HTTP401直接当作根因：补充74的account_cache_unavailable、原账号维护、Foundation目录修正及75成功。
- CircleCI说明仍把公共包job40/42写成当前pins：说明实际以job62及runtime-pins.json为准。
- 独立10GB归档工具与机器人能力混淆：机器人上限2,000,000,000字节；10GB只保留其原有合成校验证据。
- 索引指向已删除circleci-project-setup分支：改为当前相对.circleci/config.yml。
- VPS、白名单、free-pilot和旧发行文档补充明确历史范围；alpha.5仍是预览版原运行环境/Intel附件，不冒充当前架构。
- 默认main同步当前导航并标记旧代码文档的历史范围；实际运行源码不随文档变动。

旧研究和发布证据按原日期保留，不把历史失败改为成功，也不把历史成功写成当前版本重新测试。相对文件链接和原生输入不变性由独立GitHub文档检查复核。

## 没有足够依据直接删除的7个候选

以下是对其他文件的路径/文件名和Python import进行静态扫描，没有找到直接文字引用的条目。测试发现、glob、构建合约及手工入口可能不写出文件名。

| 文件 | 当前分类与保留原因 |
| --- | --- |
| .github/ops/tf_virtual_download_failure.py | 固定历史失败密文的诊断入口；位于原生输入合约目录 |
| .github/ops/tf_virtual_invite_resolve.py | 原接受之后的只读成员确认工具；保留原始证据，不执行 |
| .github/ops/tf_virtual_native_error_inspect.py | 已封存原生错误的离线诊断工具；删除会改变合约目录 |
| deploy/managed/free-pilot/host_probe.py | 旧前台运行环境探测，不属于当前生产处理 |
| deploy/managed/free-pilot/phone_drive_smoke.py | 旧显式操作者1KiB样本工具；不用于个人手机基础设施 |
| deploy/managed/free-pilot/phone_selftest.py | 旧前台合成回归工具；不在当前后台链路执行 |
| examples/target.json | 早期请求格式示例，状态不是现网任务状态 |

本轮未删这些文件。若以后移到独立研究归档，应先保留Git标签、核对旧构建/发布和动态调用，原生输入变化时重新验证公共包及pins；不能只做rm后继续复用旧原生来源。

## GitHub Actions的8条历史残留

这些工作流在生产、维护和main的当前树都没有文件，但GitHub仍登记state=active：

| 类型 | 路径 |
| --- | --- |
| 旧Drive/试验一次性工具 | check-drive-readonly-once.yml、check-drive-transfer-once.yml、check-pilot-binding-types.yml、configure-free-pilot-once.yml、deploy-verified-public-pilot-once.yml |
| 旧QQ研究 | qq-9386-inspect.yml、qq-call-inspect.yml、qq-call-record.yml |

这是Actions历史登记，不是本分支可删除的8个文件，active也不等于正在运行。本轮保留历史运行，没有自动重新启用、执行或清除；是否停用登记可作为独立UI整理，不影响本次文件检查结论。

另外5个旧生产派发/目录工作流继续disabled_manually：private-delivery、china-private-delivery、testflight-private-delivery、version-catalog、china-version-catalog。其文件和ID被离线交接及旧入口隔离核对使用，不能简单删掉来“清爽Actions”。

## 保留的较大文档

AGENTS约107KB、PROJECT-STATUS约100KB、OFFLINE-BACKEND约151KB、ZERO-COST约49KB、TESTFLIGHT及CircleCI说明各约33KB，主要是逐日证据。存在维护负担，但不是完全重复blob；AGENTS尤其包含已授权范围和禁止重复的操作。本轮补上当前摘要和历史范围，未为缩短文件而丢弃约束。后续可在逐条核对链接、来源与约束后拆出历史目录。

## 交付与验证范围

本轮改动为文档及无凭据GitHub文档检查，不编译/执行本地项目、不改变生产数据库/Secret或重新下载旧任务。维护分支可比生产分支多出文档提交；这不是生产源码漂移。生产分支必须继续等于控制面运行源码。

相对文件链接检查覆盖所有Markdown，旧分支链接专项检查及Git差异核对用于阻止意外更改原生输入。检查不验证所有外部历史网页永久可访问，不是账号、平台费用或安装运行证明。
