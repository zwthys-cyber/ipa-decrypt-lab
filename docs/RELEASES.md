# 成品包下载

当前版本为 **v0.1.0-alpha.2**，下载入口是 [GitHub Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.2)。旧版 `v0.1.0-alpha.1` 的公开 Release 和附件由本次发布替换，源码标签及历史发布说明保留。

## 选哪个包

| 文件 | 用途 |
| --- | --- |
| `ipazake-vps-linux-amd64.tar.gz` | Debian 13 x86_64 服务器端，包含 Telegram 控制器、本地 Bot API、交付加密工具和 systemd 安装文件 |
| `ipazake-runtime-macos-26-intel.tar.gz` | GitHub macOS 26 Intel 下载与解密任务的运行包 |
| `ipazake-runtime-macos-15-intel.tar.gz` | GitHub macOS 15 Intel 备用运行包 |
| `SHA256SUMS` | 发布附件的 SHA-256 |
| `BUILDINFO.json` | 源码提交、构建运行和包来源 |
| `THIRD_PARTY_NOTICES.txt` | 服务器端主要二进制依赖的许可证与来源；macOS 包内另有 licenses 目录 |
| `LICENSE` | 本项目现有的版权与使用条款 |

这些都是服务端或命令行组件，没有图形界面，不是可以安装到 iPhone 上的 IPA。

包内不含 Apple 账号、模型、交付私钥、Telegram token 或应用文件。仅下载成品包还不能完成部署，需要按 [VPS 说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/main/docs/VPS-DEPLOYMENT.md) 和 [项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/main/docs/PROJECT-STATUS.md) 配置自己的环境。控制器当前绑定本仓库，自行改为 fork 时也需要改代码并重新验证。

## 校验下载

把文件和 `SHA256SUMS` 放在同一目录。下载全部附件后，可以运行：

```sh
sha256sum -c SHA256SUMS
```

macOS 可用 `shasum -a 256 文件名`，再与清单中对应条目比较。只有部分附件时，对已下载的文件逐项核对即可。

## 版本说明

这是管理员自用流程的更新预览版，包含 Apple 新原生登录、Store AMD/SP 注册、公共 bag 上下文与商店区域字段保留、认证/许可/下载接口的设备证明兼容修复。最新版下载、指定旧版、历史列表、图标和文件命名已经接入；收费、多用户、重签名安装和实际运行兼容性还没有完成。

发布附件来自 GitHub 上通过验证的构建。服务器端在 Ubuntu 与 Debian 13 环境验证，macOS 包分别在对应 Intel 平台验证；具体运行编号写在 `BUILDINFO.json`。

公开 Release 保存的是这个版本的快照。在线任务仍使用 Actions 中按源码指纹匹配的包，不会因为发布了一个 Release 就自动切换到其中的任意附件。发布也不会自动重启或升级 VPS。

保留现有 LICENSE，这次发布没有把项目改成开源许可。第三方依赖仍按各自许可证分发。

## 重新构建与发布

所有构建与验证都在 GitHub-hosted Actions 执行。发布前固定 main 的源码提交：

1. 运行 `native-runtime-build.yml`。默认检查 macOS 26/15 Intel；发布完整双平台成品时，所选成功运行必须同时提供两个平台的精确源码指纹产物。手动单平台恢复产物不能代替完整双平台发布。
2. 若官方 Bot API 缓存缺失，先运行 `telegram-server-build.yml` 构建或从已验证的同版本公共 CI 产物恢复缓存。随后在同一个最终源码提交上运行 `vps-release.yml`，保持 `deploy=false`；等待 Ubuntu、Debian 13、systemd 和包校验全部通过。
3. 运行 `publish-release.yml`，填写 `vps_run` 和 `native_run`。前者必须来自当前发布提交的成功 build-only 运行，后者必须是成功的 main 分支原生运行包构建。
4. 发布器独立校验生产工作流身份、平台、源码指纹、artifact ZIP 摘要、包内清单、源码内容和许可证；验证后才创建草稿、上传附件并公开预览版。

本版原生构建证据为 [42439002658](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439002658)。X 的[真实下载及完整解密验证](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)通过 32 个加密切片和 86,704 页。它不等于安装运行验证，也不是发布应用 IPA；Release 只提供项目运行组件。
