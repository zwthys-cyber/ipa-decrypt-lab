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

管理员发送 App Store 链接或数字 ID → 提交前检查美区上架、免费状态和标注大小 → 固定 GitHub 工作流 → 账号授权下载 → 复用已保存模型解密 → 校验每个加密切片 → 清理 Store 账号元数据 → age 加密 → VPS 认证解包并复核摘要及 IPA 结构 → Telegram 私聊发送。

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

当前 IPA 上限为 2000 MB（2,000,000,000 字节），使用流式审计，交付前检查约 8.15 GB 可用磁盘。QQ（444934666）已通过流式审计及真实解密导出：19 切片、131440 页，341766793 字节；本轮 Telegram 文件发送仍需单独确认，见项目状态。普通重启保留本地 Bot API 状态，不重复执行云端迁移或 logOut。

## 配置与证据

Apple 账号、已有模型、Telegram 凭据与交付私钥均配置为 GitHub Secrets；VPS 仅持有 Telegram、交付密钥及限定仓库的 GitHub token。详细名称见 [部署文档](VPS-DEPLOYMENT.md)，公钥配置在 config/delivery.json。

- [真实大文件交付 41864719056](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41864719056)：92,118,013 字节，Telegram 文件确认。
- [macOS 26 样本 41876940427](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41876940427)：6 切片、164 页，验证构建缓存复用。
- [初次 VPS 部署 41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076)：Ubuntu、Debian 13、Go 与 systemd 凭据验证通过，服务启动和 Telegram 通知成功。

这些历史样本不等于迁移后新 IPA 任务已经实测。当前状态见 [项目状态](PROJECT-STATUS.md)。

最新流式审计部署：[41907700244](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907700244)，352 项测试（1 项跳过）；[QQ 真实导出 41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)通过。

## 当前容量：2000 MB

用户将直传上限定为 **2,000,000,000 字节（十进制 2000 MB）**，不支持 4 GB IPA，不启用分卷或下载链接。官方本地 Bot API 支持上传至 2000 MB，见 [Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

容量由 `tools/capacity.py` 统一定义：IPA 与单 Mach-O 上限均为 2,000,000,000 字节，Mach-O 总读取预算 4,000,000,000 字节，归档展开预算 6,000,000,000 字节，条目上限 32768。密文及外层 ZIP 另留明确封装开销；发送前再次执行严格明文大小检查。支持上限内的文件不等于所有应用均兼容。

处理前要求至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。可用应用元数据已表明超限时，在登录/下载前拒绝；元数据缺失时，下载后仍按实际大小检查。生成完成后及时删除不再需要的私有中间文件。下载超时 20 分钟、解密 15 分钟、交付加解密 10 分钟、Telegram 上传 20 分钟；GitHub worker 整体限时 70 分钟。

超限与磁盘不足通过固定 Actions 步骤标记传给机器人，使用中文提示；不读取或公开原始账号日志。发送结果未知仍不自动重发。

[发布与部署 41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129)通过 Ubuntu 和 Debian 13 各 357 项 Python 测试（1 项跳过），以及恰好 2,000,000,000 字节的 age 加密→解密→完整 SHA-256 比对和超出 1 字节拒绝测试。该大文件是 GitHub 上的合成数据，不是 2000 MB 游戏解密或 Telegram 真实上传实测。Go、systemd 凭据挂载与部署健康检查均通过。部署代码为 `4f3f79600a8f5df74c71eef6d0c03168d2895e13`。

[macOS 26 Intel 预检 41910548494](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910548494)已成功完成。独立 CMake/审计入口修复后的 [41910809719](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910809719)中 Ubuntu 与 macOS 15 Intel 已通过；记录时 ARM 任务仍在排队，不计为已通过。

## 提交前检查

机器人先显示查询提示，再检查美区上架、价格和标注大小。地区不可用、收费或已知超限时不创建 GitHub 任务、不消耗提交额度，直接显示原因。网络异常单独提示稍后重试。查询正常时通常秒级返回；超时不保证立即确认。链接的国家代码不会自动切换下载账号地区。

GitHub 手动导出也在依赖构建前检查应用条件；仍保留下载时的账号许可和实际大小校验。
