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

SQLite WAL + FULL 同步保存任务与 Telegram 更新处理意图。重复更新和进程重启不会自动重发已发送或结果不明的文件。普通重启保留本地 Telegram 状态；不得在别的机器启动同一机器人轮询。旧限时轮询和身份查询源文件已删除，部署时仍检查历史运行，防止第二个轮询进程。

管理员每日默认最多提交 20 个任务（UTC，包含失败请求），一个任务同时处理；服务配置可调整上限。未开放其他用户、自动收费或付款入口。

每小时和正常退出时保存一个私有数据库备份，用于恢复；备份在同一机器，尚非异地灾备。正在处理的文件写入私有磁盘目录，正常结束删除；异常退出遗留的本服务传输目录在下次启动清理。交付前至少保留 8,147,483,648 字节（约 8.15 GB）可用磁盘，内存上限仍为 2 GiB。

## 运维与回滚

只读检查：`systemctl status ipazake`、`/var/lib/ipazake/health.json`。日志仅含固定状态码，不输出凭据、消息正文或账号材料。启动通知确认本地 Bot API 登录和 Telegram 私聊发送，不代替真实 IPA 迁移交付测试。

回滚时先停止服务，将 current 指向 previous，按需恢复 root 私有的 bot.previous.json，再启动服务；不要同时启动 GitHub 限时机器人。

数据库不提供跨服务器同时运行的分布式锁。当前阶段仅管理员常驻内测，安装运行兼容性、真实迁移后交付及完整商业运营需分别记录。

Checks 不是 fine-grained PAT 的必填权限。遇到 Checks 权限拒绝时，服务器改用 Actions 任务/步骤状态；不再基于缺失的 Checks 证据提前交付或取消排队任务，等待正常完成后校验交付。

## 已验证的部署

[运行 41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076)在 GitHub Ubuntu 与 Debian 13 容器各通过 347 项 Python 测试（1 项环境跳过），Go 加密测试和真实 systemd 凭据挂载验证通过。最终部署的代码提交为 06bcf81fab70e597c823d1096877d3d6df4c01bd。

服务器已启用常驻服务及开机自启，健康状态 ready，Telegram 菜单回读和私聊启动消息确认成功。发布脚本会清除先前失败造成的 systemd 启动限速；当前发布不依赖已删除工作流的详情接口。启动通知和健康探针不等于迁移后新 IPA 任务的完整交付实测。

## 旧文件清理（2026-11-04）

清理提交 `a5e78c27b25a6c10efea46f9a84d0211385db503` 已通过 [GitHub 发布验证 41900942436](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41900942436)：Ubuntu 与 Debian 13 各 341 项 Python 测试（1 项跳过），Go 与真实 systemd 凭据检查成功，发布包生成成功。本轮未重新部署，VPS 仍运行先前已验证版本 `06bcf81`。

- 删除三个已退役工作流：限时 Telegram 会话、云端身份引导、Checks 恢复实验。
- 删除旧身份引导脚本、限时会话 CLI、Checks 日志模块及专用测试文件。
- 将仍使用的控制器移至 `telegram_controller.py`，更新守护进程、发布文件列表和测试引用。
- 保留并迁移 9 项控制器恢复测试到真实临时 SQLite；移除 6 项旧 Checks 专属或已有 SQLite 覆盖的测试，因此总数从 347 调整为 341。
- 现行模型、下载、解密、交付、构建缓存工作流及研究证据继续保留。已删除代码可通过 Git 历史查阅，不另存过时代码副本。

## 历史部署更新

当前代码 `8c0d4f5a2746cc9f58af04209da2837d4d12ab45` 已由 [41906318760](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41906318760)构建、部署并通过服务健康检查，Ubuntu 和 Debian 13 各 347 项测试（1 项跳过）。QQ 大型程序文件仍未通过审计，不代表已完成此任务交付。

## QQ 流式审计与真实导出已通过（2026-11-04）

[真实运行 41907705194](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907705194)成功处理 App ID 444934666：19 个加密切片、131440 页明文校验通过，清理后的 IPA 为 341766793 字节，状态 encrypted_artifact_ready，plaintext_verified=true。安装和实际运行仍未验证（runtime_verified=false）。

任务编号 `4f99d3d815873a46c93a0ec3d500f552` 保持不变。仅发布 age 密文与收据，产物 13361017588 在 2026-11-05 20:41:15 UTC 到期。原失败任务不因人工复核自动重发；管理员可在机器人私聊执行 `/get 4f99d3d815873a46c93a0ec3d500f552`。尚未把本次 Telegram 文件发送计为已确认。

审计器以 1 MiB 分块写入私有临时文件，再使用只读映射检查结构，FAT 切片使用视图而非整片复制。单 Mach-O 上限 1 GiB、总读取预算 2 GiB、归档条目 32768；IPA 总大小上限保持 1 GiB。完整成员 CRC、长度、路径、结构和明文校验保留，临时文件在正常与异常路径关闭删除。

[部署验证 41907700244](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41907700244)在 Ubuntu 与 Debian 13 各通过 352 项测试（1 项跳过），包括真实构造的 513 MiB 合成成员及 Python 跟踪内存峰值小于 16 MiB 的断言。该断言不是整个服务 RSS 的测量。Go、systemd 凭据与部署健康检查通过，VPS 已运行提交 `25c4c657d452622db5ad9c6b08790a5a30f2b2df`。全部编译与测试在 GitHub 完成。

## 当前容量：2000 MB

用户将直传上限定为 **2,000,000,000 字节（十进制 2000 MB）**，不支持 4 GB IPA，不启用分卷或下载链接。官方本地 Bot API 支持上传至 2000 MB，见 [Telegram 官方说明](https://core.telegram.org/bots/api#using-a-local-bot-api-server)。

容量由 `tools/capacity.py` 统一定义：IPA 与单 Mach-O 上限均为 2,000,000,000 字节，Mach-O 总读取预算 4,000,000,000 字节，归档展开预算 6,000,000,000 字节，条目上限 32768。密文及外层 ZIP 另留明确封装开销；发送前再次执行严格明文大小检查。支持上限内的文件不等于所有应用均兼容。

处理前要求至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。可用应用元数据已表明超限时，在登录/下载前拒绝；元数据缺失时，下载后仍按实际大小检查。生成完成后及时删除不再需要的私有中间文件。下载超时 20 分钟、解密 15 分钟、交付加解密 10 分钟、Telegram 上传 20 分钟；GitHub worker 整体限时 70 分钟。

超限与磁盘不足通过固定 Actions 步骤标记传给机器人，使用中文提示；不读取或公开原始账号日志。发送结果未知仍不自动重发。

[发布与部署 41910544129](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910544129)通过 Ubuntu 和 Debian 13 各 357 项 Python 测试（1 项跳过），以及恰好 2,000,000,000 字节的 age 加密→解密→完整 SHA-256 比对和超出 1 字节拒绝测试。该大文件是 GitHub 上的合成数据，不是 2000 MB 游戏解密或 Telegram 真实上传实测。Go、systemd 凭据挂载与部署健康检查均通过。部署代码为 `4f3f79600a8f5df74c71eef6d0c03168d2895e13`。

[macOS 26 Intel 预检 41910548494](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910548494)已成功完成。独立 CMake/审计入口修复后的 [41910809719](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41910809719)中 Ubuntu 与 macOS 15 Intel 已通过；记录时 ARM 任务仍在排队，不计为已通过。

## 提交前检查与旧发布自动清理（2026-11-04）

机器人在创建任务、写入恢复记录和占用日额度之前，用无账号 App Store 查询核对美区上架、免费状态及标注大小。未通过会直接说明原因；网络错误不当成地区不匹配。查询使用 8 秒网络超时、2 MiB 响应预算，不自动重试、不跟随重定向。

手动触发 GitHub 导出也会在拉取外部源码和编译之前检查。[闲鱼 510909506 复核 41919666036](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41919666036)预期拒绝 app_not_found_in_us，查询约 0.58 秒，整个作业约 18 秒；全部依赖构建、账号访问和解密步骤跳过。正常机器人拒绝发生在 GitHub dispatch 之前，不需要等待运行器。尚不支持中国区账号下载。

[发布 41919936183](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41919936183)在 Ubuntu 与 Debian 13 各通过 371 项测试（1 项跳过）、2000 MB age 流式验证及 systemd 凭据验证，部署与健康检查成功。

`deploy/prune_releases.py` 在新服务健康确认后仅保留 current 和 previous 指向的版本；只删除 releases 下符合提交 SHA 命名的真实旧目录，不跟随符号链接，不接触数据库、凭据、传输或 Telegram 状态。重复部署同一版本保留原回滚目标。清理异常只报告延后，不把健康部署当成失败。

本次实际删除 6 个旧版本，服务器仅余 2 个发布目录，总计约 100 MiB。检查时传输临时目录约 4 KiB、Telegram 总状态约 44 KiB、系统 journal 约 8.1 MiB；没有发现遗留的大 IPA。状态为 ready，task_active=false。正常临时传输在结束时删除，异常残留在下一次启动清理，审计临时文件随关闭/进程退出释放。数据库和单份恢复备份保留；未配置额外的全系统日志清空操作。
