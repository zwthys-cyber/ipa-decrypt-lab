# VPS 部署

编译和测试都在 GitHub 上执行，VPS 只运行验证过的成品。服务器负责 Telegram、任务记录和文件交付；Apple 下载及 FairPlay 解密仍由 GitHub macOS 处理。

当前部署环境为 Debian 13、x86_64、4 GB 内存的服务器。systemd 给机器人服务设置了 2 GiB 内存上限。交付前还会检查至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。

## 获取成品

[Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases) 提供 Linux amd64 服务器包。它是命令行和 systemd 服务，不是桌面安装程序，也不带账号配置。

需要重新构建时，运行 `vps-release.yml`，默认 `deploy=false`。工作流会完成 Python 回归、Go 加密测试、真实 systemd 凭据挂载检查和 Debian 13 容器兼容性验证，然后生成无凭据的发布包及 SHA-256。

设为 `deploy=true` 后，才会在同一轮验证通过后通过 SSH 安装到配置的 VPS。发布公开版本时使用 build 模式，不借发布操作重启线上服务。

## GitHub Secrets

| 名称 | 用途 |
| --- | --- |
| `VPS_HOST` | VPS 地址 |
| `VPS_SSH_PASSWORD` | 部署时使用的 SSH 凭据 |
| `VPS_KNOWN_HOSTS` | 独立核对过的 SSH 主机公钥 |
| `VPS_GH_TOKEN` | 限定到当前仓库，Actions read/write、Contents read |
| `TELEGRAM_BOT_TOKEN` | 机器人 token |
| `TELEGRAM_OWNER_ID` | 管理员数字 ID |
| `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` | 本地 Bot API 所需应用凭据 |
| `DELIVERY_AGE_IDENTITY` | 与仓库交付公钥匹配的私钥 |

Apple 账号及模型仍由 GitHub 工作流读取，不复制到 VPS。现有交付私钥也不应为重试而重新生成，否则无法解开先前的交付产物。

Checks 不是 fine-grained token 的必填权限。缺少 Checks 读取权限时，控制器改用 Actions 的任务与步骤状态，等工作流完成后再校验和交付。

当前控制器的工作流/API 目标固定为本仓库。自行部署到 fork 前，需要调整代码中的仓库目标并重新通过构建验证；仅修改 token 并不能切换目标。

## 安装和运行

安装器先校验包摘要，然后安装 Python、Pillow 和必要的系统运行库，不在 VPS 安装编译器或执行测试。程序放到版本目录，通过 current 链接切换，同时保留上一版程序和配置。

| 路径或服务 | 用途 |
| --- | --- |
| `ipazake.service` | 非 root 常驻服务，开机启动、异常重启 |
| `/opt/ipazake/current` | 当前程序 |
| `/opt/ipazake/previous` | 上一版程序 |
| `/etc/ipazake/bot.json` | root 私有配置，通过 systemd LoadCredential 注入 |
| `/var/lib/ipazake/state.sqlite3` | 私有任务数据库 |
| `/var/lib/ipazake/health.json` | 服务健康状态 |

安装脚本的参数和凭据交接由 `vps-release.yml` 负责。不要把未配置的发布包直接当作完整部署，也不要在公开命令行里粘贴 token 或密码。

仅运行一个机器人轮询进程。数据库和文件锁负责单机恢复，不能用于两台服务器同时运行同一个机器人。普通重启保留本地 Bot API 状态，不重复执行云端迁移或 logOut。

## 备份与清理

SQLite 使用 WAL 和 FULL 同步。每小时及正常退出时生成一份私有恢复备份，目前仍在同一台服务器；异地备份还没接入。

正常传输结束会删除临时文件，异常残留在服务下次启动时清理。发布成功且健康检查通过后，旧程序目录只保留 current 和 previous。数据库、备份和凭据不参与这项清理。

每日默认最多提交 20 个下载任务（包含失败任务），同一时间处理一个。新版本查询另有配额，见 [Telegram 说明](TELEGRAM.md)。

## 检查与回滚

可以先查看：

```sh
systemctl status ipazake
cat /var/lib/ipazake/health.json
```

日志只记录固定状态码，不输出账号或消息正文。健康状态 ready 表示服务已启动，不表示某个 IPA 已发送完成。

回滚时先停止服务，把 current 指向 previous，按需恢复 root 私有的 bot.previous.json，再启动服务。不要同时启动另一个轮询器。文件发送结果不明时，先查看聊天记录，再决定是否用 `/get` 取回。

## 验证记录

在 [41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076) 完成首次部署和服务健康验证；带历史列表的版本部署记录为 [41940545752](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41940545752)，对应提交 `772d7dfe173815cbb3d19f3609624af29a1db18c`。

预编译运行包的升级只切换了 GitHub 上的下载和查询流程，没有重新部署 VPS。公开 Release 的构建记录与源码提交会写入 `BUILDINFO.json`；发布成功不代表线上服务已自动切换到该版本。
