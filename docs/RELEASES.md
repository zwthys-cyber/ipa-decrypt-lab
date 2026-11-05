# 成品包下载

第一版以 **v0.1.0-alpha.1** 发布，下载入口是 [GitHub Releases](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.1)。

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

这是目前管理员自用流程的第一个公开成品版本。最新版下载、指定旧版、历史列表、图标和文件命名已经接入；收费、多用户、重签名安装和实际运行兼容性还没有完成。

发布附件来自 GitHub 上通过验证的构建。服务器端在 Ubuntu 与 Debian 13 环境验证，macOS 包分别在对应 Intel 平台验证；具体运行编号写在 `BUILDINFO.json`。

公开 Release 保存的是这个版本的快照。在线任务仍使用 Actions 中按源码指纹匹配的包，不会因为发布了一个 Release 就自动切换到其中的任意附件。发布也不会自动重启或升级 VPS。

保留现有 LICENSE，这次发布没有把项目改成开源许可。第三方依赖仍按各自许可证分发。
