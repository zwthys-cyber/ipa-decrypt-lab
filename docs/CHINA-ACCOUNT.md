# 中国区账号的独立接入

**中国区真实登录、跨运行器 Cookie 刷新、免费原包下载和授权数量查询已通过；独立模型、解密与机器人地区路由仍未完成。** 原德国区账号、默认线路和安全设置保持原样，当前正式服务仍为 alpha.4。

## 凭据与实时验证码

仓库 [Actions Secrets](https://github.com/zwthys-cyber/ipa-decrypt-lab/settings/secrets/actions) 中的 `APPLE_CN_ID`、`APPLE_CN_PASSWORD`、独立稳定的 `APPLE_CN_GUID` 和 `APPLE_CN_SESSION_B64` 只用于中国区账号，不覆盖原账号 Secrets。最后一项保存受保护的账号会话。

验证码不提前填入登录任务。先启动 `china-account-auth.yml` 的 `authenticate` 模式；原生客户端发起登录后，保持同一个 Authenticator 实例及进程等待，最长五分钟。看到经验证的等待请求后，才获取新验证码，临时存入 `APPLE_CN_2FA_CODE`，并通过 `china-otp-relay.yml` 提交。公开输入只有任务编号和随机请求标识，不能填验证码、账号或密码。验证码以绑定任务、源码和有效期的 age 密文传回等待中的进程，经标准输入提交一次；中继完成后删除临时验证码 Secret。超时、被拒绝或会话中断后停止，不自动反复登录。

初始登录成功则无需验证码。明确的验证要求或歧义 BadLogin 可以进入一次人工尝试，但歧义 BadLogin 本身不能证明二次认证状态或密码错误。原账号拒绝安全升级的约束继续有效。

## 会话保护与复用

真实返回必须属于新账号且 storefront 为中国区 `143465`，不修改地区标签或回退旧账号。现有账号邮箱只供首次登录监督程序比较身份不同，不传给客户端。原始认证输出不进入日志或附件。

成功会话只在 GitHub runner 内处理，使用仓库 Secrets 公钥封装为 `APPLE_CN_SESSION_B64` 的密文候选附件。核实可信任务成功、国家、源码、运行包和附件来源后，才将该密文写入对应 Secret。会话明文、令牌和验证码不公开，VPS 不接收 Apple 会话。退出时清理中国区本地缓存。

在新的 GitHub 运行器上直接使用旧令牌下载，曾在免费许可阶段遇到原生 Store 设备证明失败。独立的 `resume-cn` 命令携带保存的 Cookie 做一次正常认证刷新，获得当前运行环境的设备证明后，再下载免费样本。此路径已在一次新的运行器上成功，不需要本次再次输入验证码；它仍然发起认证请求，不能描述为完全不登录或永久免验证码。会话过期、密码或安全状态变化后仍可能需要重新验证。

## 工作流与验证边界

- `china-account-auth.yml` 默认 `test`；`authenticate` 做一次独立实时登录，不下载应用或恢复模型。
- `cn-auth-runtime.yml` 在 GitHub-hosted macOS 26 Intel 构建、测试和重定位独立客户端及 GitHub 公钥封装工具。默认德国区运行包和登录命令不变。
- `china-download-check.yml` 默认 `preflight`；只检查固定小型免费中国区样本。`download` 尝试原令牌，`resume-download` 先做一次 Cookie 刷新，再下载并校验样本包身份。只保留数字回执及仓库公钥封装的刷新会话，不上传应用，也不发送 Telegram 文件。
- `china-session-check.yml` 的 `query` 做一次只读授权数量查询；`native-query` 使用原生设备证明。未观测到数量时不进行模型初始化或占用电脑授权名额。HTTP 500 不等于密码错误或整个会话失效。

所有编译、测试和验证都在 GitHub-hosted Actions 执行。原账号密码、模型和状态不挂载到这些中国区任务。没有账号撤销、账号安全升级、VPS 部署或默认线路切换。

## 已验证证据

| 阶段 | 证据 | 结果 |
| --- | --- | --- |
| 实时验证码中继 | [42547699795](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547699795) | 密文中继成功，临时验证码 Secret 已删除 |
| 真实登录 | [42547602116](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42547602116) | 同一原生会话完成认证，地区为中国区，会话已独立保存 |
| Cookie 刷新运行包 | [42548393225](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42548393225) | 26 项 Swift、Go 封装工具及重定位验证通过 |
| 无账号合成检查 | [42548395352](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42548395352) | 28 项 Python、2 项 Node 通过；后续 pod 校验增加到 29 项 Python |
| 新运行器原包下载 | [42548840372](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42548840372) | App ID `1530340312`，中国区，2,500,837 字节；正常 Cookie 刷新，未再次使用验证码，更新会话已封装保存；样本已清理 |
| 授权数量检查 | [42549102362](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42549102362) | 匹配认证服务节点、Cookie 和客户端标识后仍返回 HTTP 500；没有占用或撤销电脑授权 |

## 授权数量兼容修复与模型工具

摘要接口返回 HTTP 500 的兼容因素已通过对照定位：[42550766669](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42550766669) 保持同一保存会话和只读查询，仅改用历史兼容的 Configurator/2.17 客户端标识，返回 HTTP 200，授权电脑数为 **0**。登录和普通下载继续使用当前已验证的 2.21 标识，只将账号摘要查询切回兼容标识。固定查询验证 [42551097522](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42551097522) 也通过。此前的 500 不能据此归因于密码、验证码、账号限制或接口全面故障。

模型基础工具 [42551095068](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42551095068) 已通过构建、29 项 Swift 检查、独立 CN 模型/状态/GUID 密封工具检查、原生 I/O/响应契约及无账号的真实请求构造预检。合成和私密会话边界检查 [42551823926](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/42551823926) 通过 41 项 Python 与 2 项 Node 检查。带实时模型登录支持的新运行包仍需完成对应生产验证。

`china-model-bootstrap.yml` 默认为 `preflight`。`trial` 先验证固定免费原包、完整输入结构、可用授权数量、原生设备标识和请求绑定，才允许发起一次中国区模型初始化。原生绑定使用该初始化运行器真实设备标识；如需调整中国区 GUID，先只在当前运行器内使用，只有受保护状态/模型阶段通过并核实密文候选后才保存，不改德国区标识。模型任务如被要求二次验证，会保留同一 Authenticator 并使用现有实时密文中继，不提前填写过期验证码。

模型产物目的地严格固定为 `FAIRPLAY_CN_MODEL_B64` 和 `FAIRPLAY_CN_STATE_B64`；新模型仍需对中国区原包做完整明文验证。初始化后先保护可重放状态，再做恢复，避免恢复失败后再次占用名额。存在中国区检查点时拒绝重复初始化，改用显式 `replay`，该模式不提交授权请求。仅保存检查点的任务会明确报告“模型恢复待完成”，不能写成解密已成功。原账号密码、模型和状态不挂载到中国区任务。

**授权数接口已恢复，中国区模型目前处于预检和初始化准备阶段。** 实际模型恢复、完整解密校验、历史版本和正式机器人路由仍待完成。不得未经兼容性验证将德国区模型用于新账号；成功下载原包不能证明解密、安装或实际运行。
