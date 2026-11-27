# 验证记录

记录日期：2026-11-27。此页保存当前实现所依据的可追溯证据，供维护和复核使用。日常操作见[使用指南](TELEGRAM.md)。

## 生产部署

| 项目 | 记录 |
| --- | --- |
| 最近成功切换 | [GitHub Actions 45923827277](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45923827277) |
| 部署源码 | `977b239ee2e35c908361109c8d0e10d1fa252873` |
| 通过项 | 同源码 webhook、真实定时触发、历史状态读回及交接封存 |
| 本次变更 | 首页与按钮精简、未完成历史条目隐藏、回复输入提示 |

之后的文档维护提交不代表新的生产部署。精确运行源码以最新成功切换回执及 readiness 回读为准。

## 真实应用处理

| 应用 | 执行来源 | 已验证结果 |
| --- | --- | --- |
| Go Club | [CircleCI job72](https://app.circleci.com/workflow/aa787787-32bb-4c8f-a9de-5776666cc997/job/ef34d39f-955e-45a9-aee8-a6b60bb4a0ba)，源码 `f3451dd2ba31ac9d9524da4ed7b6ad8f22c1346a` | 6 个加密镜像、8,000 页；73,172,295 字节私有文件及通知已确认 |
| 红果漫剧 | [CircleCI job75](https://app.circleci.com/workflow/2ae89675-bc82-451c-b290-4ee63c2c360a/job/a1e13406-0c02-43ec-a679-5a5bfa77fd53)，源码 `185a52110922e0f67ac2c7dff4e1fa85b3b4c98e` | 17 个加密镜像、120,976 页；342,632,968 字节私有文件及通知已确认 |

红果漫剧该次全程约 4 分 23 秒，其中排队约 50 秒。这是单次测量，耗时会受队列、应用大小和网络影响。

上述任务覆盖获取、完整明文校验、账号数据清理、私有上传和通知。应用重签名、安装与运行不属于这些结果的证明范围。两次任务的文件和通知均保留，不因文档维护而重复执行。

## 界面与控制面

[控制检查 45923579560](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45923579560) 在部署源码上通过 88 项集成检查、16 项兼容检查及 5 项结构/呈现检查，覆盖分页、归属、取消、去重、输入提示失败隔离等行为。

用户截图已确认此前版本的首页、已完成列表和历史导航。最新精简及输入提示已通过 CI 和部署检查；客户端中的短暂显示仍取决于实际交互及响应时间。

## 国区会话与公共包

- [账号维护 45917018396](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917018396)：原账号登录成功，没有使用验证码。
- [保存会话复用 45917154187](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917154187)：原生只读检查成功；没有电脑授权或撤销。
- [Foundation 缓存检查 45917974219](https://github.com/zwthys-cyber/ipa-decrypt-lab/actions/runs/45917974219)：验证隔离目录绑定，随后由真实任务75验证。
- 公共 base/CN/TF 包的生产者、原生输入及摘要以[固定清单](../deploy/managed/circleci/runtime-pins.json)为准，目前指向 CircleCI job62。

## 尚待实测

当前平台的完整历史版本交付、新 TestFlight 请求和真实上传中断恢复仍需各自实测。旧平台的成功记录保存在[历史档案](archive/README.md)，保持其原始验证范围。

历史交接中读回 29 条任务、89 条 updates 和 14 条 metadata；两条 pending 保持 held。无法直接观察源服务物理停机，source_disabled_verified 保持 false。已通过凭据与派发隔离完成切换，源保全之后的未知变化仍保留缺口。
