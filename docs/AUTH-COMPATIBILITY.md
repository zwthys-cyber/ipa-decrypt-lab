# 可选认证兼容模式

来源比较：AssppWeb 固定提交 485be0b884e5d88bbd5379179064999992273614 的 frontend/src/apple/authenticate.ts，与 ipatool 固定提交 d9c0247daea564d3ec7d04a9b015d0a29af66b04 的登录请求构造。

plist-compat 仅修改 Content-Type 为 application/x-apple-plist，无验证码的 attempt 为4，有验证码为2。保持 Apple bag 选出的认证地址、签名器、TLS校验和凭据处理不变；不降级为无签名请求。上游默认模式保留。

新增 Go 测试验证实际请求的头部、密码/验证码拼接、attempt 和目标地址不变。认证通用 BadLogin 的诊断修正对两种模式均生效。

这是一项基于公开实现差异的受控对照，尚无真实登录成功证据。不能仅凭替换字段就宣称兼容问题已解决。每次只执行所选模式，失败后不自动遍历其他模式或无限重试。

参考：https://github.com/Lakr233/AssppWeb/blob/485be0b884e5d88bbd5379179064999992273614/frontend/src/apple/authenticate.ts
