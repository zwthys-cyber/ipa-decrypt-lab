# 常驻 VPS 部署

用户已允许服务器运行 GitHub 构建、测试通过的成品。编译和测试仍全部在 GitHub；Apple 下载及 FairPlay 解密继续在 macOS Actions 上执行。

## 构建与部署

运行 `vps-release.yml`，默认 `deploy=false`：完整 Python 测试、Go 加密测试、Debian 13 容器兼容性测试后，生成无凭据的 Linux amd64 发布包和 SHA-256。

`deploy=true` 在同一轮验证通过后，通过固定 SSH 主机密钥部署。服务器仅安装 Python 与系统运行库，不安装编译器、pip 依赖或运行测试。安装器验证发布包摘要，保留上一版目录与配置，原子切换 current 链接。

必要 Actions Secrets：
- VPS_HOST：服务器地址。
- VPS_SSH_PASSWORD：部署 SSH 凭据；仅本次部署传输使用，不进入服务配置。
- VPS_KNOWN_HOSTS：已独立连接确认的 SSH 主机公钥。
- VPS_GH_TOKEN：仅本仓库的 fine-grained token，Actions read/write、Contents read。
- 复用已有 Telegram 凭据、管理员 ID 和 DELIVERY_AGE_IDENTITY。Apple 凭据及模型不复制到服务器。

## 运行方式

systemd 服务 `ipazake.service` 使用独立无登录用户，开机启动、异常重启，内存上限 2 GiB。程序目录只读，私有数据位于 `/var/lib/ipazake`。服务凭据由 systemd LoadCredential 注入，源文件 `/etc/ipazake/bot.json` 仅 root 可读。

SQLite WAL + FULL 同步保存任务与 Telegram 更新处理意图。重复更新和进程重启不会自动重发已发送或结果不明的文件。普通重启保留本地 Telegram 状态；不得在别的机器启动同一机器人轮询。成功切换后关闭旧的 telegram-session 工作流。

管理员每日默认最多提交 20 个任务（UTC，包含失败请求），一个任务同时处理；服务配置可调整上限。未开放其他用户、自动收费或付款入口。

每小时和正常退出时保存一个私有数据库备份，用于恢复；备份在同一机器，尚非异地灾备。正在处理的文件写入私有磁盘目录，正常结束删除；异常退出遗留的本服务传输目录在下次启动清理。交付前至少保留 6 GiB 可用空间。

## 运维与回滚

只读检查：`systemctl status ipazake`、`/var/lib/ipazake/health.json`。日志仅含固定状态码，不输出凭据、消息正文或账号材料。启动通知确认本地 Bot API 登录和 Telegram 私聊发送，不代替真实 IPA 迁移交付测试。

回滚时先停止服务，将 current 指向 previous，按需恢复 root 私有的 bot.previous.json，再启动服务；不要同时启动 GitHub 限时机器人。

数据库不提供跨服务器同时运行的分布式锁。当前阶段仅管理员常驻内测，安装运行兼容性、真实迁移后交付及完整商业运营需分别记录。

Checks 不是 fine-grained PAT 的必填权限。遇到 Checks 权限拒绝时，服务器改用 Actions 任务/步骤状态；不再基于缺失的 Checks 证据提前交付或取消排队任务，等待正常完成后校验交付。
