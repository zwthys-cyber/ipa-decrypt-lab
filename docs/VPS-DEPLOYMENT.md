# VPS 部署

编译和测试都在 GitHub 上执行，VPS 只运行验证过的成品。服务器负责 Telegram、任务记录和文件交付；Apple 下载及 FairPlay 解密仍由 GitHub macOS 处理。

当前部署环境为 Debian 13、x86_64、4 GB 内存的服务器。systemd 给机器人服务设置了 2 GiB 内存上限。交付前还会检查至少 8,147,483,648 字节（约 8.15 GB）可用磁盘。

## 获取成品

[v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5) 提供 Linux amd64 服务器包。它是命令行和 systemd 服务，不是桌面安装程序，也不带账号配置。

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

Apple 账号密码、明文会话、设备私有材料及 FairPlay 模型仍由 GitHub 工作流使用，不复制到 VPS；TF 的持久会话密文例外，见下文状态清单。现有交付私钥也不应为重试而重新生成，否则无法解开先前的交付产物。

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

在 [41899775076](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41899775076) 完成首次部署。简洁首页和选中后收起列表的部署记录为 [42145258538](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42145258538)，对应运行代码提交 `957783d42f0d605bb455384827c01e7a73037027`，服务健康检查通过。

预编译运行包的升级只切换了 GitHub 上的下载和查询流程，没有重新部署 VPS。公开 Release 的构建记录与源码提交会写入 `BUILDINFO.json`；发布成功不代表线上服务已自动切换到该版本。

## 本版升级与发布边界

2026-11-08 登录兼容修复运行在 GitHub macOS 下载组件中，X 的下载和完整明文验证已恢复。它不需要把 Apple 凭据、模型或设备证明放到 VPS。当前控制器仍调用 main 分支工作流，自动使用精确匹配的新原生运行包。

公开发布新版 Linux 包与实际部署是两个动作：`vps-release.yml` 的 `deploy=false` 只构建验证，`publish-release.yml` 只验证并发布附件。此次成品更新不自动部署 VPS。要升级线上控制器，仍需单独运行经过验证的部署流程并检查服务健康，数据库和上一版配置继续保留。

完整发布操作、`vps_run` / `native_run` 的来源要求及附件校验，见[成品包说明](RELEASES.md)。


公共 Bot API 缓存缺失时，可运行 `telegram-server-build.yml` 重新构建固定版本。若仍有相同固定版本的已验证 VPS 公共产物，也可填写 `reuse_vps_run`：恢复步骤必须验证成功的 main 生产工作流、上游固定版本缓存键、artifact ZIP 摘要、包摘要和源码提交，只取出公共 Bot API 二进制并再次检查版本。它不恢复账号、模型、凭据或旧版项目源码。缓存恢复完成后，重新运行最终源码提交的 `vps-release.yml` 完整验证。


## 进度卡升级

main 新增流程步骤比例、真实下载字节计数和完整耗时。VPS 通过既有 Actions read 权限读取经过摘要、任务、run 和源码绑定验证的小型进度快照，Checks 仍不是 PAT 必填权限。独立刷新线程只负责编辑进度消息，在阻塞取回、复核或上传期间继续计时。

升级需要匹配的原生运行包，以及经过 Ubuntu/Debian 13 验证的新控制器部署；公开 alpha.2 包仍为此前版本快照。不要只更新 VPS 而让新源码缺少匹配原生包。实际文件发送结果不明的记录仍保持人工确认，不因进度升级重发。

进度卡控制器已在 [42443436341](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443436341) 部署，服务源码为 `d59f3eb8ebd6f8ce0c98bfb0909817bc4345ac22`，健康检查通过。随后 [42443709848](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443709848) 用固定到 Node.js 24 的官方 Actions 重新通过服务器构建和 Ubuntu/Debian 13 检查；这次 build-only 没有再次重启服务。Node.js 24 是 GitHub Actions 的依赖运行时，不是新增的 VPS 安装要求。该阶段匹配原生包见 [42443706492](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42443706492)，实际导出与数字计数见[项目状态](PROJECT-STATUS.md)。

## 后端导出提速（2026-11-08）

[运行包 42445031389](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42445031389) 加入仅限 GitHub 的 raw ZIP 成员复制清理，替代导出阶段的 Python 全包重复压缩；[实际 X 导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42445425200) 通过全部检查。它不改变 VPS 的解密、恢复或 Telegram 发送协议，无需为此重启当前服务。旧 VPS 的 delivery-crypt 继续使用 decrypt 命令，新 scrub 命令在 VPS 模式下被拒绝。源码指纹校验仍生效，不能混用不匹配的包。

## 白名单版本升级

alpha.4 增加 `multi_user.py` 服务模块，现有六项凭据保持不变。管理员仍由 `TELEGRAM_OWNER_ID` 固定；白名单保存在现有私有 SQLite 中，默认没有其他用户。不要把用户 ID 列表加入仓库、发布附件或公开日志。

服务只启动一个轮询进程，使用全局更新游标和全局下载/查询准入；每用户任务、列表和进度独立。旧管理员作用域保持兼容，备份整库即可同时保留 ACL 和所有恢复记录。先完成 GitHub 上的 Ubuntu/Debian 13、双平台运行包与发布验证，再安装已验证成品。部署不会自动给任何额外用户授权。命令和配额见[白名单说明](MULTI-USER.md)。

白名单版已在 [42543133206](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42543133206) 完成实际安装和健康检查，运行源码为 `b92dc1575123e1b7eab2283b62d355539fc71e4d`。构建在 Ubuntu/Debian 13 各运行 466 项 Python 测试（各跳过 1 项）及 Node/Go/systemd 检查。没有添加其他线上用户或替换六项凭据；管理员按需授权即可。[alpha.4 公开附件](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.4) 已完成来源和摘要校验。

## 私有权限与交付状态的只读诊断

`private-access-inspection.yml` 用于管理员明确指定目标后的运行检查：工作流参数仅为随机 nonce，目标身份及预期请求经短时 `IPAZAKE_PRIVATE_INSPECTION` Secret 传递。不要把真实用户 ID 或私有记录放入公开输入、源码、运行标题或附件。

`.github/ops` 中的诊断器先在 GitHub-hosted runner 运行合成测试，再通过固定主机密钥的 SSH 只读查询已验证服务源码、健康状态、授权及私有任务/进度记录；VPS 不运行测试套件或编译。输出限定为角色、额度、状态和布尔值，不回显用户、聊天、任务、消息 ID 或凭据。检查不调用 Telegram、不改变授权、不部署/重启服务。该历史诊断器固定检查当时的 b92dc157 源码，不适用于当前 d53f7def 部署；再次使用前必须重新审查限定并通过 GitHub 验证。

[42544535030](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42544535030) 已确认一个真实普通用户的 delivered、独立作用域和最终进度 done。检查结束清理远端/runner 私有临时文件，并删除临时诊断 Secret。该操作工具不进入运行包或原生运行源码指纹，不需要为只读检查重发 Release。

## 中国区链接路由（alpha.5）

控制器包新增 `account_profile.py`，按 `/cn/` 链接选择固定中国区工作流，数字 ID 与其他地区链接仍使用原外区工作流。普通国区任务只在 GitHub macOS 26 Intel 使用独立 CN 运行包。上线前需要新的双平台默认运行包和匹配 CN 运行包均成功，避免缺包影响任务。

VPS 的六项凭据及私有 SQLite 原样保留；不要向服务器复制 Apple 账号密码、明文会话、GUID、检查点或模型；后续 TF 会话密文的持久保存见下节。CN Secrets 只配置在 GitHub，见 [中国区说明](CHINA-ACCOUNT.md)。既有白名单、全局配额和单轮询进程约束继续适用。

[alpha.5 部署 42566050391](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42566050391) 已完成安装和实际 ready 健康检查，运行源码 `48ad5b75eb61a6cc5f01ffb539f06a33055adc9a`。构建/部署在 GitHub 完成 Ubuntu/Debian 13 各 480 项 Python、Node/Go/systemd 与包检查；服务器只安装运行成品，原 SQLite、白名单和六项凭据保留。

## TestFlight 状态与部署门禁（2026-11-09）

TF 接入已部署到现有控制器，最新部署为 [42714903713](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42714903713)，运行源码 `d53f7defdc65fb11e5b3c04ac3e612990ed6430c`，服务 ready 健康检查通过。此前交付绑定修正版为 [42710092658](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42710092658)。新 TF 文件使用 `名称_Beta_版本.ipa`，App Store 命名不变。发布流程先在 GitHub 验证当前源码的两种 Intel 基础运行包、CN 变体、TF 原生组件及真实无发送导出证明，再经既有固定 SSH 安装已测试成品。VPS 不编译、不运行测试，也不做 FairPlay 内容解密。

- `/var/lib/ipazake/testflight/session.age`：原独立虚拟 Mac 身份与 TF 上下文的持久密文。VPS 状态助手不解封此文件；GitHub worker 才临时解封。
- `/var/lib/ipazake/testflight/acceptance.sqlite`：首次需要接受新邀请时创建的持久意图；含原邀请码的历史接受保护。不得删除或清空来重试未知 POST。
- `/opt/ipazake/testflight-state.py`：CI 测试过的密文/意图助手，只允许固定的状态、保存、声明及结果记录操作，不登录或调用 Apple。
- 原有 `state.sqlite3`、白名单、私有发送记录及 `tf-private-return.sqlite` 均保留；最后一个文件保护此前已确认的单次回传，不能重置重发。

会话持久保存不等于延长 Apple 的服务端有效期。拒绝访问时任务明确停止；不会依赖旧的一天期研究 artifact 重新生成身份。新会话维护需保持原身份和未知意图保护，不隐式更换账号。TF 普通任务只挂载已保存会话的解封钥匙、既有 CN 模型和所需传输凭据；原 CN/外区账号 Secrets、模型与授权数量不变。
