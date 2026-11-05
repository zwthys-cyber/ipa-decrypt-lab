# 第二阶段验证记录

> 在这里保留早期原生接口和合成样本的实验记录。后续模型恢复与真实 IPA 校验已经通过，最新进展见 [项目状态与使用说明](PROJECT-STATUS.md)；本文保留原始失败证据。

验证提交：`3b4adddd913778fcdcc9ba45ecb92bbe7d0cf61b`

[GitHub Actions 验证运行](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41713104024)

## 已完成证据

- ARM macOS、Intel macOS 与 Linux：原生程序编译通过，二进制契约测试和 IPA 包检查测试通过。
- Intel macOS 的原生 remap 合成试验：调用实际发生，返回 -1，errno=45，未完成映射读取，未产生解密结果。
- Darwin 的 errno=45 对应 ENOTSUP，即操作不受支持。该结果来自特定 GitHub 运行器、特定合成调用，不推广为所有 Mac 或所有真实应用的结论。
- ARM macOS 的同一原生 remap 合成试验：调用实际发生，返回 -1，errno=1（EPERM，操作不被允许），未完成映射读取，未产生解密结果。
- 三个平台 Actions 最终均为 success：这里的成功只代表构建、契约测试和诊断正常完成，不代表原生解密成功。

## 试验范围

使用的样本完全由程序生成，不含 Apple 授权记录，不使用 Apple 账号、个人手机、真实 IPA 或第三方服务。原生 API 对此样本拒绝，不是应用授权失败的完整诊断，也不能证明登录账号后一定可行。

IPA 包检查器只验证结构、读取边界、架构和加密标志。它不验证原始明文、不运行应用、不修复签名，也不会输出可以安装的 IPA。

## 当时接下来要解决的问题

1. 找到在基础设施限制下可运行、可验证的授权与解密路径。GitHub 编译机和原生函数符号本身不是账号凭据。
2. 在不将真实应用或账号信息公开到此仓库和日志的前提下，确定可用的测试数据与结果验证方式。
3. 通过已知正确数据或独立运行验证证明明文正确。不得只凭 cryptid=0、字节变化、API 返回0或CI绿色宣告成功。
4. 上述门槛未通过前，不提供收费解密结果、不启用收费假任务流程、不承诺独立解密任意 App Store 应用。

## 系统约束

所有构建、测试、试运行仅在 GitHub-hosted Actions。无 Debian 项目运行、无个人手机节点、无第三方收费 API。当时还没有部署服务器常驻服务；后来接入的 VPS 方案见 [部署说明](VPS-DEPLOYMENT.md)。

参考：[Apple errno.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/errno.h)、[Apple kern_mman.c](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_mman.c)。

## 第三阶段：原生接口对照结果

[验证运行](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41714295084)。三个平台构建和测试全部通过。

| GitHub 运行器 | cryptid=0 不加密控制 | cryptid=1 应用加密 | cryptid=2 模型加密 |
| --- | --- | --- | --- |
| macos-15 ARM | 返回0，映射可读 | 返回-1，errno=1 | 返回-1，errno=1 |
| macos-15-intel | 返回0，映射可读 | 返回-1，errno=45 | 返回-1，errno=45 |
| ubuntu-24.04 | 不支持原生接口 | 不支持原生接口 | 不支持原生接口 |

控制组证明当前调用入口及基础映射路径可以执行。两种加密路径在无授权合成样本上均被拒绝。此结果仍不能确定真实应用所缺的具体授权条件，也不能证明登录账号或重签名就能解决。没有真实明文解密证据。

当时遇到的瓶颈已经从编译转为有效授权环境及真实数据验证。继续增加解析器或合成测试无法替代这一门槛。所有试验保持仅 GitHub Actions 执行。
