# 项目状态与使用说明

更新日期：2026-11-04。当前阶段：**GitHub-only 模型获取、真实 IPA 解密校验及跨运行器复用已完成验证**；真实 IPA 私有加密导出已验证，Telegram 限时集成测试正在接入；生产服务尚未部署。

## 已完成的三条路径

本轮固定测试 App ID 为 **6599842047**，三次运行均使用 GitHub-hosted macOS。

| 路径 | 实际结果 | 新增电脑授权 | 证据 |
| --- | --- | --- | --- |
| 首次恢复模型 | 下载原始 IPA、取得授权状态、恢复模型，再独立复核完整 IPA | 本次一次，数量 3 → 4 | [41846142942](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846142942) |
| 直接复用模型 | 全新运行器读取模型 Secret，重新下载并验证 | 不调用电脑授权 | [41846974302](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41846974302) |
| 从检查点恢复模型 | 全新运行器读取保存的 SIDB/IOMAC 数据，重新恢复模型并验证 | 报告明确为 `authorization_request_attempted=false` | [41847775765](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41847775765) |

三次均完成 **62 个加密切片、12,524 个页面**的明文校验，最终 `decryption_proven=true`、`plaintext_verified=true`。这些数量是本轮样本的记录，不是对其他应用或未来版本硬编码的通过门槛；实际校验要求覆盖审计器发现的全部加密切片，并核对可用的加密前页面哈希。

经验证的实现提交为 [b668df0](https://github.com/zwthys-cyber/ipa-decrypt-lab/commit/b668df099334706a9f02e6bcaf56ff553b023c8b)。后续状态整理为文档更新。

## 现在如何使用

### 常规解密验证：使用已保存模型

1. 打开 [Independent Swift Store trial](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/native-store.yml)。
2. 点击 **Run workflow**，分支选择 `main`。
3. 将 `decryption_backend` 明确选择为 **`offline`**，再执行。

该入口目前默认选择 `native`，其用途是原生诊断；常规模型验证需要手动选择 `offline`。现有手动工作流的测试目标是 App ID 6599842047。

通过标准是最终报告 `status=offline_plaintext_verified`、`decryption_proven=true`、`plaintext_verified=true`。单独的构建成功、Secret 编码检查成功或下载成功不代表解密校验成功。

### 需要重新恢复模型：使用授权检查点

打开 [Private same-runner model bootstrap](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/workflows/model-bootstrap.yml)，选择 `main` 和 **`mode=checkpoint-replay`**。

该模式从 `FAIRPLAY_STATE_B64` 恢复私有临时文件，并使用归档硬件标识完成模型推导，不向新主机的系统目录导入授权，也不调用机器授权。最终应为 `model_recovered_and_verified`，且两个明文校验标志均为 true。

该工作流各模式的含义：

| 模式 | 用途 | 账号操作 |
| --- | --- | --- |
| `preflight` | 构建、合成测试和环境检查；默认值 | 不使用 Apple 账号 |
| `input-inspection` | 下载并检查原始 IPA 的许可格式 | 使用现有账号下载，不调用机器授权 |
| `checkpoint-replay` | 从保存的状态重新恢复模型并验证 | 使用现有账号下载，不调用机器授权 |
| `trial` | 首次生成新的授权状态并恢复模型 | 会提交一次机器授权请求，可能占用名额 |

本仓库已有可复用模型和检查点，日常验证使用 `offline`；重新推导模型使用 `checkpoint-replay`。无需为重复验证选择 `trial`。

## 已配置的私有数据

| Secret 名称 | 用途 |
| --- | --- |
| `APPLE_ID` | 已配置的下载账号 |
| `APPLE_PASSWORD` | 该账号的密码 |
| `FAIRPLAY_MODEL_B64` | 已通过完整 IPA 校验的模型 |
| `FAIRPLAY_STATE_B64` | 固定 SIDB/SIDS 文件和必要硬件标识，用于重放恢复 |

模型和状态 Secret 已于 2026-11-04 14:22:53 UTC 保存。文档不包含它们的值。

工作流仅输出使用仓库公钥封装的模型/状态密文，**不会自行写入或覆盖仓库 Secret**。本次保存由已授权的 GitHub API 操作完成。重放产生的新模型密文未覆盖已经验证可复用的模型 Secret。

最新直接测得的电脑授权数量为 **4/5**，来自首次成功恢复试验；这是记录值，不是实时查询。此前用户批准的全部解除授权只执行过一次（5 → 0），不会作为常规重试清理步骤。

## 尚未完成的部分

- **IPA 交付**：真实私有加密导出已通过 [41856194867](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41856194867)，移除账号元数据后的文件为 92,118,013 字节；只保留一天 age 密文，明文仍不公开。Telegram 大文件发送需要单独确认回执。
- **安装运行**：尚未验证重签名、安装和实际运行，`runtime_verified=false`。
- **扩大兼容范围**：其他应用、账号、版本及真实 Linux 平台解密尚未完成实测；已有 Linux 构建与合成测试不能代替这些证据。
- **独立签名信任验证**：页面哈希校验不等同于独立的 Apple CMS 信任验证。
- **产品与部署**：用户已恢复 TG 接入。管理员私聊 /id 已完成真实收发；提交、查询、取消及私有文件回传代码和合约测试已接入。启动方法见 [Telegram 私有交付测试](TELEGRAM.md)。计费和常驻生产服务尚未完成。

## 进一步阅读

- [仓库首页](../README.md)：结果概览和工作流目录。
- [完整研究记录](../OFFLINE-BACKEND.md)：各阶段成功与失败证据、固定依赖和验证边界。
- [下载接口实现](../ENT-DOWNLOAD.md)：原始 IPA 下载链路。
- [项目约束](../AGENTS.md)：仅 GitHub 执行、私有数据保护及用户设定。
