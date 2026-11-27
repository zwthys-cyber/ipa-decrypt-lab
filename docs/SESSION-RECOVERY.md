# 任务恢复

任务和意图持久保存于 D1，工作机运行结束后仍可核对状态。恢复以跟踪既有操作为原则，避免重复提交或通知。

## 去重与取消

- 真实输入绑定固定请求号，外部提交前先保存意图。
- 定时触发核对已有运行，并按串行规则推进等待任务。
- 提交、邀请接受或通知结果不明时，保留原状态，不自动再次执行。
- 取消意图先持久化，确认工作机终止后才释放容量。
- 已确认的文件和通知不自动重新发送；重新领取由接收人明确发起。

历史列表隐藏已结束的未完成条目，只影响显示。后台任务及意图仍保留，用于恢复和核对。

## 历史交接

已有任务、更新游标、版本浏览信息和已知文件/通知记录已经读回。两条历史 pending 继续保持 held，最后保全之后的源变化仍存在未知缺口。

TestFlight 历史确认使用固定原始证据构造并封存，没有通过重新接受邀请补齐记录。稳定密钥、原意图和已确认私有回传记录均须保留。

无法直接观察的源服务物理停机状态保持如实标记。不得伪造停机时间、清空未知结果或创建空账本来满足恢复条件。

## 会话与文件

保存会话不延长服务端有效期。普通任务不自动使用密码、旧验证码、替代身份或新的电脑授权来恢复访问。

文件领取仍需通过归属、完整性、私有权限及领取窗口检查。数据库中存在记录不保证文件持续可领取，也不代表它已自动删除。

当前发布与核对流程见[维护手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md)，精确来源见[验证记录](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/VALIDATION.md)。原始恢复细节保存在[状态档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/archive/2026-11-27/PROJECT-STATUS.md)。
