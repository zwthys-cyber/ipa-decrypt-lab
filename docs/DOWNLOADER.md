# 下载与校验

应用处理由按需 macOS ARM64 工作机执行。工作机加载已经验证的运行包，普通请求不编译项目。

## 处理流程

1. 校验链接、地区、免费价格和容量，绑定请求的 App ID 与版本。
2. 核对公共运行包的来源、摘要、原生输入及平台兼容性。
3. 恢复所需账号会话和已有模型，取得原始应用包。
4. 复核目标、版本和包结构，验证受保护页面的预加密 CodeDirectory 哈希。
5. 清理账号数据，核对 ZIP、CRC 和输出摘要。
6. 私有上传后，由控制面独立核对文件归属、权限、名称、大小和 SHA-256。
7. 保存确认结果，向接收人发送文件入口。

当前 App Store IPA 上限为 2,000,000,000 字节。独立 Linux 归档工具的 10 GB 合成验证属于不同能力，详见[工具说明](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/free-pilot/LINUX-ARCHIVE.zh-CN.md)。

## 完整性要求

所有受保护页面必须通过严格校验。目标或版本不匹配、缺少明文证明、账号数据清理失败、文件摘要或权限不符都会终止交付。

成功结果证明的是应用导出和交付，安装及运行验证另见[项目状态](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/PROJECT-STATUS.md)。

## 实现入口

- [工作机编排](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/managed_worker.py)
- [App Store 适配](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/appstore_worker.py)
- [TestFlight 适配](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/tf_worker.py)
- [控制面](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/runtime-api.mjs)
- [公共运行包来源](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/deploy/managed/circleci/runtime-pins.json)

相关操作见[使用指南](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/TELEGRAM.md)，兼容性调查见[下载档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/archive/2026-11-27/DOWNLOADER.md)。
