# Linux 授权归档完整性验证工具

> 本工具的10GB合成归档能力独立于当前机器人的2,000,000,000字节IPA上限，不代表10GB应用下载或网盘传输已通过。[当前运行手册](../../../docs/OPERATIONS.md)。

校验依赖实际字节和摘要。Drive 上传后的校验允许服务重新标注普通文件的媒体类型，并继续比对名称、大小、SHA-256、归属和私有权限。

这是独立、无网络、只读的 Python 3 工具。它适用于已合法取得且有权处理的 IPA/ZIP 文件；不下载 App Store 应用，不处理账号，不改变保护机制，不修改或签名 IPA。

- ZIP/ZIP64 有界目录预检：最大原始文件 10,000,000,000 字节，最大声明解压量 30,000,000,000 字节。
- 1 MiB 分块读取成员并核对 CRC 与声明大小，再分块计算原始归档 SHA-256。
- IPA 只检查单一顶层 Payload/*.app/Info.plist 布局，不验证 plist 内容、签名、来源、安装能力或保护状态。
- 拒绝非普通文件、符号链接、非私有文件、路径异常、损坏归档和检查期间发现的文件变化。
- 无额外 Python 依赖；在 GitHub-hosted Ubuntu 上使用合成样本构建和测试。
- [最新 CI](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45663099506)在 Linux amd64 和 ARM64 上完整读取并校验了逻辑大小为 10 GB 的合成 ZIP64 归档。真实 10 GB 网盘传输和生产性能仍待验证。

## 在有权使用的 Linux 执行环境运行

```sh
sha256sum -c SHA256SUMS
python3 archive-verify.pyz /private/Example.ipa --confirm-authorized-file
```

可加 `--expected-sha256` 并提供从可信来源独立取得的 SHA-256。仅打开文件读取，不生成或修改 IPA。输入文件应由当前执行用户拥有，且权限仅允许所有者访问（例如 0600）。成功输出 JSON，失败返回退出码 2。不要把私人文件摘要或文件名公开。此包不是原生解密引擎，也不是已经部署的机器人或免服务器运行环境。


## 上传前的完整校验

同版本的 private_upload.py 会在发起 IPA/ZIP 上传前运行完整归档校验，保留原始字节并复用计算出的 SHA-256。检测到输入变化时停止，不自动重新创建上传任务。原有私有 journal 和续传协议保持不变。CI 另用逻辑大小恰好 10 GB 的稀疏合成 ZIP64 文件执行真实分块读取、CRC、独立 SHA-256 比对及超限拒绝；只记录合成测量值，不发布该文件。该测试不代表真实网盘上传、生产性能或原生解密能力。


## 独立 Linux 运行包（双架构）

CI 在 GitHub 标准 Ubuntu x86_64 和 ARM64 runner 上分别构建并验证两个 Python zipapp：

- archive-verify.pyz：完全离线，只读归档校验。
- private-upload.pyz：已有的操作员私有上传程序及归档依赖。仅在可信、获授权的 Linux 运行环境使用，须明确确认账号与文件权限；支持原来的私有 journal、完整校验与断点续传。GitHub Actions 环境仍拒绝实际上传。

BUILDINFO 记录源码提交、验证的架构及 Python 版本。两种架构分别运行完整 10 GB 稀疏合成样本测试和独立包回归测试；未成功的架构不视为已验证。打包工具不包含 Apple 原生组件或真实凭证，不提供计算宿主，也不代表生产传输或解密已通过。
