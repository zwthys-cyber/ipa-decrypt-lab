# 零费用版：独立测试环境部署

本指南用于当前 v0.2 免费控制层试验版，并不代表线上 IPA 服务已迁移。只测试自己有权处理的文件。原 VPS、线上机器人、Apple 账号、原任务数据库和密钥保持不变。

## 1. 从 GitHub 获取部署包

打开升级 PR 对应的 Managed runtime contracts 工作流。synthetic、workerd、pilot_bundle 都通过后，在 Artifacts 下载 free-pilot-deployment-*。校验 BUILDINFO 中的源码提交及 SHA256SUMS。不要使用历史失败构建或不匹配的源码包。

部署包内容：

- worker.mjs：已合并依赖的独立 ES module，可在 Worker 网页编辑器中使用。
- schema-fresh.sql：仅供全新、独立、空的 D1 数据库一次初始化。
- migrations/：已有测试库按顺序升级时使用，不得重复执行已应用迁移。
- wrangler.example.json：CLI 配置示例，默认关闭入口、关闭链接功能、数据库 ID 为占位符。
- private_upload.py、zip_preflight.py、private_cleanup.py：操作员工具，不在 Worker 或 GitHub Actions 上执行。

## 2. 创建隔离的 Cloudflare Free 环境

打开 https://dash.cloudflare.com/ ，确认使用 Workers Free 计划。不要绑定任何计费订阅，不启用 R2、Containers、付费 Workers 或自动升级。若页面要求付费或无法确认免费条件，停止部署。

在 D1 SQL Database 中创建全新数据库 ipazake-free-pilot。打开 Console，执行 schema-fresh.sql，检查 pilot_jobs 和 pilot_links 已存在且数据为空。此脚本不能用于原生产数据库或已经初始化的测试库。若执行失败，不要在不清楚迁移状态时重复执行整个脚本。

在 Workers & Pages 创建新的独立 Worker ipazake-free-control-pilot。将部署包内的 worker.mjs 完整复制到网页编辑器的 ES module 中，保存并部署。添加 D1 binding，变量名必须是 DB，选择刚创建的独立数据库。网页编辑器可能更适合桌面浏览器；不保证所有移动端编辑操作可用。

在 Settings 的 Variables and Secrets 中设置普通变量 PILOT_ENABLED=0、PILOT_LINK_ENABLED=0。确认不启用 Version/Preview URL。需要测试时才启用独立 Worker 的 workers.dev 免费子域名，不需要购买域名。此时对 /telegram 的未授权 POST 应为 503，GET 应为 404。不要在生产机器人的 token 上设置 webhook。

## 3. 独立测试机器人（未配置时保持关闭）

使用 BotFather 创建新的测试机器人，不使用原机器人。生成至少 43 字符、仅由字母数字、下划线、短横线组成的随机 webhook 密钥。通过 Cloudflare 私有 Secret 输入 TELEGRAM_WEBHOOK_SECRET，另设 PILOT_OWNER_ID 为自己的 Telegram 数字 ID。不要把任何 token 放入 GitHub 提交、聊天记录、URL 或截图。PILOT_ENABLED=1 只在测试机器人、独立数据库及 Secret 均已确认时开启。

测试机器人的 Telegram setWebhook 调用需要将 Worker 的 HTTPS /telegram 地址及同一个 secret_token 作为参数，allowed_updates 仅设 message。使用自己的可信终端或私有部署工具；不在浏览器地址栏拼接 token，不使用第三方在线调用器。检查 webhook 状态并在私聊测试 /start、数字 App ID、/status、/cancel。此阶段只登记任务，不触发真实下载。

## 4. Google Drive 链接试验

确认个人免费 15 GB 共享容量、无付费账单或自动升级。仍需同一 Google OAuth 应用的短期 drive.file access token；ChatGPT 的 Google Drive 连接不等于此应用获得该 token。不得向聊天发送 access token、refresh token、机器人 token 或账号密码。请先用独立的、自己拥有的合成小文件做试验。

Worker 增加私有 Secret PILOT_LINK_ISSUER_TOKEN、PILOT_DRIVE_ACCESS_TOKEN、PILOT_DRIVE_RECIPIENT_EMAIL，并仅在已授权的小文件测试时开启 PILOT_LINK_ENABLED=1。操作员上传工具需要相同 Google 账号、短期 OAuth 授权和私有持久记录；它目前要求一个可信 Linux/macOS 执行环境，不能在 Worker 内运行，也不使用 GitHub Actions 作为生产计算服务。详见 docs/ZERO-COST.md 中 Phase 6 至 10。/get 只在文件元数据和访问权限核验后返回私有链接；两小时领取限制不代表网盘权限自动过期。

## 5. 验收和停止条件

必须取得实际测试机器人私聊回执、实际 D1 记录、授权合成文件上传和下载的 SHA-256 匹配，才可称链接交付已现场验证。真实 10 GB 传输、免费执行资源及原生处理仍未验证。账号未授权、免费计划不明、OAuth 过期、空间不足或测试失败时停止，不购买任何资源。原 VPS 不关停，不迁移原生产 token 或历史状态，不将此试验版合并部署到线上。

参考：
- https://developers.cloudflare.com/d1/get-started/
- https://developers.cloudflare.com/d1/best-practices/remote-development/
- https://developers.cloudflare.com/workers/platform/pricing/
- https://core.telegram.org/bots/api#setwebhook
- https://developers.google.com/workspace/drive/api/guides/api-specific-auth


## 6. 可选：Google OAuth 自动刷新（新增 Worker 版本）

本功能仅适用于升级后并通过 CI 验证的 Worker。保持 PILOT_ENABLED=0 和 PILOT_LINK_ENABLED=0，直到独立测试环境配置完毕。用户可以在自己的 Cloudflare Worker 的 Secrets 界面直接配置 PILOT_DRIVE_CLIENT_ID、PILOT_DRIVE_CLIENT_SECRET、PILOT_DRIVE_REFRESH_TOKEN 及已有的 PILOT_DRIVE_RECIPIENT_EMAIL。不要通过聊天、源码、URL 或跨平台自动复制传递凭证。三项 OAuth 配置不完整时，程序拒绝请求，不会退回旧访问令牌。

仅在已获授权的链接登记或查询需要访问 Drive 时，Worker 才向 Google 官方 token 接口请求新的短期 Access Token，并检查返回的 Bearer 类型及明确的 drive.file 授权范围。访问令牌只在该次请求内使用，不写入 D1，也不记录到日志。没有扩大授权范围、后台定时刷新或自动重新授权。若 Google 不返回明确的范围，或令牌已撤销/过期，试验版会停止链接操作。Google 外部应用 Testing 状态的 Refresh Token 仍有七天限制；本功能不绕过该限制。操作员上传工具暂时仍需要短期 Access Token，未实现自动刷新。此阶段没有执行真实 OAuth 请求、改变线上机器人、迁移凭证或开启计费。


## 7. 操作员上传端的短期令牌自动刷新

新版 private_upload.py 与 private_cleanup.py 支持同一 OAuth 应用的三项环境配置 PILOT_DRIVE_CLIENT_ID、PILOT_DRIVE_CLIENT_SECRET、PILOT_DRIVE_REFRESH_TOKEN 和接收人邮箱。只在可信、已获授权的操作员执行环境配置，不从 Cloudflare 读取或导出 Secret。访问令牌保存在当前进程内，到期前刷新；无完整刷新配置时才允许旧的手动 Access Token 模式。不自动重试失败写入，使用原有私有 journal 恢复。invalid_grant 会停止操作，必须由用户重新授权。不得在 Actions 上执行真实上传或清理。

Google OAuth Testing 模式的授权有效期有限。用户可在 Google Auth Platform 的 Audience 页面按官方要求决定是否发布应用，发布后重新授权；这不保证令牌永不失效。继续使用 drive.file 最小授权，不启用计费或扩大权限。

## 8. Linux 上传前完整性门禁

同一部署包中的 private_upload.py 依赖 archive_verify.py 与 zip_preflight.py；三个文件须保持同一 CI 来源。IPA/ZIP 默认执行完整成员 CRC、大小和原始 SHA-256 检查，验证失败时不发起上传；检查期间或分块传输时发现文件变化则停止，保留恢复状态。其他普通文件仍使用原有分块 SHA-256。仅在有权使用的可信执行环境进行真实上传，不使用 Actions 提供生产文件传输。
