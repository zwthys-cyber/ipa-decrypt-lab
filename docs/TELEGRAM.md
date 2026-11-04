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

管理员发送美区免费 App Store 链接或数字 ID → 固定 GitHub 工作流 → 账号授权下载 → 复用已保存模型解密 → 校验每个加密切片 → 清理 Store 账号元数据 → age 加密 → VPS 认证解包并复核摘要及 IPA 结构 → Telegram 私聊发送。

账号仍须具备下载许可。缺失验证材料、下载失败或摘要不匹配时拒绝交付。原始 IPA、模型、账号材料不发布到公开仓库或公开产物；公开密文保留一天。IPA 安装、签名兼容性及运行未验证。

当前一次处理一个任务，每 UTC 日默认最多 20 个提交（含失败任务），提交间隔至少 30 秒。默认 macos-26-intel，备用 macos-15-intel；只有确认原运行未执行且已终止时才能切换，每个逻辑任务最多两次。模糊提交结果不得自动重发。

## 私聊指令

| 指令 | 行为 |
| --- | --- |
| /start 或 /help | 使用说明 |
| /decrypt | 提示输入链接或 App ID |
| App Store 链接或数字 ID | 创建任务 |
| /id | 显示管理员自己的数字 ID |
| /status | 查看当前任务 |
| /cancel | 请求取消当前任务 |
| /get 任务编号 | 显式取回尚未过期的完成文件 |

菜单由常驻服务启动时注册并读回核对，不再单独运行旧 menu 会话。SQLite 保存更新处理意图和任务状态；重启恢复跟踪，不重复提交下载。发送结果不明时不会自动重发，应先确认聊天再使用 /get。[恢复规则](SESSION-RECOVERY.md)。

## 进度与交付

同一张进度卡显示真实阶段、任务编号与已用时间。同阶段约 15 秒刷新，/status 可主动刷新。上传接口没有可靠逐字节回调，因此不估算进度百分比；仅 Telegram 确认文件发送成功后显示 100%。

Checks 读取无权限时使用 Actions 任务与步骤信息；缺少可信 Checks 证据时，不提前交付或主动取消排队任务，等待工作流正常完成后验证。存在可信且绑定请求/运行/提交的 artifact_ready check 时，仍须验证已完成加密产物和所有摘要才能提前交付。

当前 IPA 限为 1 GiB，归档最多 32768 条，单 Mach-O 最多 512 MiB，审计总读取预算 2 GiB；交付前要求至少 6 GiB 可用磁盘。QQ（444934666）实测仍超过单 Mach-O 上限，尚不能交付，见项目状态。普通重启保留本地 Bot API 状态，不重复执行云端迁移或 logOut。

## 配置与证据

Apple 账号、已有模型、Telegram 凭据与交付私钥均配置为 GitHub Secrets；VPS 仅持有 Telegram、交付密钥及限定仓库的 GitHub token。详细名称见 [部署文档](VPS-DEPLOYMENT.md)，公钥配置在 config/delivery.json。

- [真实大文件交付 41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：92,118,013 字节，Telegram 文件确认。
- [macOS 26 样本 41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)：6 切片、164 页，验证构建缓存复用。
- [初次 VPS 部署 41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076)：Ubuntu、Debian 13、Go 与 systemd 凭据验证通过，服务启动和 Telegram 通知成功。

这些历史样本不等于迁移后新 IPA 任务已经实测。当前状态见 [项目状态](PROJECT-STATUS.md)。
