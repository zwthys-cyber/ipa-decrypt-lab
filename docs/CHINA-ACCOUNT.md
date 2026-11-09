# 中国区账号的独立接入

新增账号分阶段接入。现有德国区账号、默认线路和安全设置保持原样。中国区登录、会话复用、下载及独立解密模型分别验证，不能把其中一步的成功等同于完整接入。

## 凭据与实时验证码

仓库 [Actions Secrets](https://github.com/zwthys-cyber/ipa-decrypt-lab/settings/secrets/actions) 中的 `APPLE_CN_ID`、`APPLE_CN_PASSWORD` 和独立稳定的 `APPLE_CN_GUID` 只用于新账号，不覆盖原账号 Secrets。

验证码不提前填入登录任务。先启动 `china-account-auth.yml` 的 `authenticate` 模式，原生客户端发起登录后保持同一个 Authenticator 实例及进程等待，最长五分钟。看到经验证的等待请求后，才获取新验证码，临时存入 `APPLE_CN_2FA_CODE`，并通过 `china-otp-relay.yml` 提交。中继的公开输入只有任务编号和随机请求标识，不能填验证码、账号或密码。验证码通过绑定任务、源码和有效期的 age 密文传回正在等待的客户端，经标准输入提交一次；中继完成后删除临时验证码 Secret。超时、验证码被拒绝或会话中断后停止，不自动反复登录。

初始登录已成功则无需验证码。明确的验证要求或歧义 BadLogin 可以进入一次人工验证码尝试，但歧义 BadLogin 本身不能证明账号已开启二次认证，也不能证明密码错误。原账号拒绝安全升级的约束继续有效。

## 验证与会话保护

`china-account-auth.yml` 默认 `test`，仅在 GitHub-hosted runner 执行无账号合成测试。`authenticate` 使用来源、平台及源码指纹匹配的独立中国区客户端；原有默认运行包和登录命令不变。不下载 IPA，不恢复模型，不执行机器授权或账号撤销，也不更新 VPS 服务。

客户端仅接收中国区凭据；旧账号邮箱只供监督程序比较新旧账号不同。真实返回必须属于该账号且 storefront 为中国区 `143465`，不修改地区标签或回退原账号。原始认证输出不进入日志或附件。

成功后的会话只在 GitHub runner 内处理，使用仓库 Secrets 公钥封装为 `APPLE_CN_SESSION_B64` 的密文候选附件。只有核实可信任务成功、账号地区及附件来源后，才可将该密文写入对应 Secret。会话明文、令牌和验证码不公开，VPS 不接收中国区 Apple 会话。退出时清理中国区本地缓存。保存会话不保证永久免验证码，后续失效仍需正常重新验证。

## 当前证据与待办

- [42547323101](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547323101)：18 项 Python 和 2 项 Node 测试通过，覆盖进程保持、迟到验证码、超时停止、来源/有效期校验和上传器凭据隔离。合成成功不代表真实 Apple 登录成功。
- 带 GitHub 公钥会话封装工具的独立原生构建 [42547161993](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547161993) 尚待完成核实。
- 用户暂缓更新验证码，尚未启动新的实时登录窗口。此前两次单次诊断未取得有效中国区会话，不能据此判断普通 App Store 下载能力或二次认证状态。
- 真实登录、受保护会话复用、中国区元数据/历史目录、下载及独立模型仍待验证。不得未经兼容性验证将德国区模型用于新账号。
