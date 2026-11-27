# 发行说明

当前公开预览版为 [v0.1.0-alpha.5](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.5)。

该版本保存历史架构的 Linux 服务端与 macOS Intel 运行包。当前线上服务使用 Cloudflare / CircleCI 架构，运行来源见[验证记录](VALIDATION.md)，维护方式见[操作手册](OPERATIONS.md)。

## 附件

| 文件 | 用途 |
| --- | --- |
| ipazake-vps-linux-amd64.tar.gz | 历史 Debian x86_64 服务端 |
| ipazake-runtime-macos-26-intel.tar.gz | 历史 macOS 26 Intel 运行包 |
| ipazake-runtime-macos-15-intel.tar.gz | 历史 macOS 15 Intel 运行包 |
| BUILDINFO.json | 附件的源码和构建来源 |
| SHA256SUMS | 附件校验和 |
| THIRD_PARTY_NOTICES.txt / LICENSE | 依赖来源与使用条款 |

附件不含账号、模型、机器人凭据或应用 IPA。

## 校验

将下载文件与 SHA256SUMS 放在同一目录，Linux 可使用：

```sh
sha256sum -c SHA256SUMS
```

macOS 可使用 `shasum -a 256 文件名`，与清单逐项比对。准确构建来源以附件 BUILDINFO 为准，源码标签不代表后续重打包的全部内容。

## 版本与维护

发布附件不会自动切换线上服务。当前服务按固定来源加载 ARM64 公共运行包；历史附件的重新构建流程保存在[发行维护档案](archive/2026-11-27/RELEASES.md)。

各预览版说明见[历史档案目录](archive/README.md)。
