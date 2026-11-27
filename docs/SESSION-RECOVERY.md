# 当前任务恢复与历史交接

核对日期：2026-11-27。现网持久化位于Cloudflare D1，Apple处理在按需CircleCI工作机；不再依赖原运行环境私有SQLite或同机备份恢复日常任务。具体源码与发布顺序见[运行手册](OPERATIONS.md)。

## 新任务的恢复规则

- 每个真实Telegram输入绑定固定请求号和pilot_任务号；先记录意图再提交外部工作。Webhook重投不能生成第二个任务。
- D1记录派发、运行、上传、取消、通知和TF接受状态；cron核对已有外部run并按串行规则推进等待任务，不盲目重新POST。
- dispatch_unknown、未知TF接受和未知通知不会因时间过去而自动变成可重试。确认通知只发送一次，不能为演示再下载/再通知。
- /status按进行中、已完成、历史记录分组分页，每页3项，通过按钮更新原消息。/cancel必须带任务号；确认工作机结束前保留占位，找不到run不等于没执行。
- /get仅在归属、完整文件证明、Drive私有权限和领取窗口都通过时返回链接；窗口当前为注册后24小时，不等于Drive权限自动撤销。
- 失败后修复原因，再由主人发出新的真实输入；不自动重放失败、已取消、已完成或发送不明任务。

## 不可用原运行环境的离线交接

[成功切换45918215266](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45918215266)对应生产处理源码`185a52110922e0f67ac2c7dff4e1fa85b3b4c98e`，验证已封存的29条旧任务、89条updates、14条metadata，原offset/browser和已知私有文件/通知保留。2条旧pending保持held；备份保全后无法取得的源变化仍是未知缺口，不宣称全量无缺口。

旧TF接受账本未找到时没有创建空库冒充来源；按固定原接受、后续成员确认、原加密意图和已知运行清单构造历史confirmed tombstone并seal，没有重新接受。稳定HMAC和原私有回传记录须保留。

原bot使用独立新Token，旧Token已拒绝，5个旧派发/目录工作流停用；新webhook及每个新源码自己的cron必须通过回读。无法观察旧机物理停机，source_disabled_verified=false，不能伪造stopped_at或把供应商停机提示当成服务停机证明。

切换前消息进入持久隔离，不当作新下载；保留历史行不等于重新发送旧文件。GoClub和红果漫剧的已确认交付也不自动重复。

## 会话与故障分类

保存Apple会话不延长服务端有效期，普通任务不能以恢复名义自动密码登录、使用旧验证码、重建身份或注册电脑。2026-11-27原国区会话维护单独获得授权并完成；Foundation缓存路径问题已修复并由真实任务75验证。

cn_session_requires_maintenance仅是通用退出错误；account_cache_unavailable应先排查HOME/CFFIXED_USER_HOME，不能直接归因为账号失效。源码/运行包/模型/版本不匹配均明确停止，不清空意图绕过保护。

## 历史资料和验证范围

旧SQLite/WAL、VPS文件锁、白名单及SSH接受许可实现保存在[该文档固定源码档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/185a52110922e0f67ac2c7dff4e1fa85b3b4c98e/docs/SESSION-RECOVERY.md)，仅用于旧架构追溯。它们仍被兼容构建与测试引用，不代表现网恢复依赖旧机。

新控制面由workerd/D1集成检查覆盖，CircleCI75真实国区任务证明17镜像/120,976页及私有上传/通知；新平台真实历史版本交付、新TF任务与上传中断恢复仍需对应实测。CI合成故障测试不等于所有真实故障情景已经发生。
