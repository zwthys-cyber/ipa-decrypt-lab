# 认证诊断

先确认失败阶段，再选择维护方式。登录、许可、下载、模型处理和文件交付是不同阶段，单个通用错误不能替代完整诊断。

## 常见分类

| 现象 | 检查方向 |
| --- | --- |
| account_cache_unavailable | 检查隔离账号缓存及 HOME / CFFIXED_USER_HOME 绑定 |
| cn_session_requires_maintenance | 这是通用退出错误，需要结合固定诊断类别；不能直接判定会话过期 |
| HTTP 401 / 403 | 核对接口、会话和请求上下文；单个状态码不独自说明密码或模型问题 |
| generic BadLogin | 原因尚不明确，不据此断言开启了双重认证 |
| 运行包缺失或来源不符 | 核对 pins、生产者、原生输入及主机 ABI |
| 免费许可或地区不可用 | 区分商店、账号许可和客户端环境，保留原生诊断的固定类别 |
| 明文或归档校验失败 | 保留原请求，检查模型、版本和校验报告，不降低校验要求 |

## 当前认证路径

客户端基于固定来源的 ApplePackage，使用原生 Apple 配置与 Store AMD 证明，保留商店区域及请求上下文。配置请求清理账号认证信息，账号请求继续绑定指定 Apple 接口。

原生设备证明中的 SP 处理与 FairPlay 电脑授权分开判断。不得将一次协议成功当作完整登录、许可或解密成功。

国区普通任务复用保存会话。独立维护入口位于 main；使用新的验证码或替换会话前，应核对对应授权。TestFlight 使用自己的保存会话，不以 App Store Cookie 代替。

## 诊断材料

公开日志仅记录固定错误类别、布尔值和有限计数。账号、Cookie、原始响应、私有路径及链接留在相应 CI 私有环境。

故障恢复顺序见[维护手册](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/OPERATIONS.md)，真实修复证据见[验证记录](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/VALIDATION.md)，协议兼容调查见[历史档案](https://github.com/zwthys-cyber/ipa-decrypt-lab/blob/upgrade/managed-runtime-maintenance-v0.2/docs/archive/2026-11-27/AUTH-COMPATIBILITY.md)。
