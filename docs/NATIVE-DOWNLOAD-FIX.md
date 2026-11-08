# 原生下载流程修正


> 2026-11-08 文档复核：保留首次 Swift 下载修正的历史原因；当前版本另已补齐 Store AMD/SP、公共 bag 上下文和区域字段兼容。 当前成品为 [v0.1.0-alpha.2](https://github.com/zwthys-cyber/ipa-decrypt-lab/releases/tag/v0.1.0-alpha.2)；[X 完整导出](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42439908718/attempts/2)已通过 32 个加密切片和 86,704 页校验。操作入口见[文档索引](DOCUMENTATION.md)，安装运行仍须另测。


这是在首次 Swift 登录成功后，对下载流程的修正记录。

在首次独立 Swift 试验中登录成功（无需验证码），随后下载失败：
https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/41727238337

因此可以确认当前凭据在这条客户端链路中能完成登录，不应继续把所有问题归因于双重认证。

检查源码时，发现下载命令会在刚登录成功后无条件重新认证，并在目标应用缺授权时直接抛错。改为复用刚建立的会话；遇明确 licenseRequired 时，只对当地商店已确认 price==0 的免费应用获取许可并重试一次。外层仍检查官方 US 元数据免费；两处免费检查同时生效。不自动同意账号安全升级或新的条款。

新增下载失败分类，所有上游原始输出仍在内存内处理，不转发账号或授权信息。当时还需要真实下载验证；后续成功记录见 [原始下载结果](../NATIVE-DOWNLOAD-RESULTS.md)。
