# 中国区账号

## 选择地区

带 `/cn/` 的完整 App Store 链接使用国区账号。其他地区链接和数字 App ID 使用默认账号，系统不会从数字 ID 猜测地区。

国区历史版本查询及指定版本也需要保留完整链接：

```text
/versions https://apps.apple.com/cn/app/id1661733229
/version https://apps.apple.com/cn/app/id1661733229 1.18.1
```

可用范围见[项目状态](PROJECT-STATUS.md)。

## 会话与模型

普通任务使用已保存的国区会话、GUID、checkpoint 和模型，并核对账号及商店绑定。它不会自动切换到外区账号、获取验证码或注册新的电脑授权。

会话维护独立于下载任务，在 main 的[账号维护工作流](../.github/workflows/china-account-auth.yml)执行。需要维护时先核对错误阶段；2026-11-27 已单独批准并完成的维护，不构成今后任意重新登录的授权。

macOS 原生工具需要同时设置 HOME 与 CFFIXED_USER_HOME，确保读取隔离目录中的账号缓存。

## 许可与兼容性

免费应用能否取得仍取决于商店、账号许可和客户端环境。红果漫剧已通过当前平台的完整交付验证；这一结果不代表其他国区应用的地区许可问题均已解决。

历史抖音任务在许可阶段失败，其原因尚未由单一变量对照确定。遇到类似情况应保留任务编号和错误阶段，按[认证诊断](AUTH-COMPATIBILITY.md)处理。

具体运行证据见[验证记录](VALIDATION.md)，完整研究过程见[国区档案](archive/2026-11-27/CHINA-ACCOUNT.md)。
