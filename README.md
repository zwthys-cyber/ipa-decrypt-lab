# IPA Decrypt Lab

自主研发的 IPA 解密引擎可行性原型。**尚未完成真实 App Store IPA 解密验证，不是已可收费的服务。**

## 固定约束

- 代码直接提交 GitHub；所有编译、测试、验证和试运行只在 GitHub-hosted Actions。
- 不在用户 Debian 服务器或编辑工作环境构建、安装项目依赖、执行项目代码或部署服务。
- 不使用用户个人 iPhone / TrollStore，不依赖第三方收费解密 API。
- 公开仓库只保存源码与合成测试数据；禁止上传真实 IPA、Apple 账号、凭据和 Bot Token。
- Actions 用于限时研发验证，不作为 TG 商业服务的长期运行主机。

## 本阶段交付

独立 C 实现，无第三方解密库：

1. 严格解析 thin little-endian 64-bit Mach-O 及其加密命令。
2. macOS / Intel macOS / Linux 编译与合成契约测试。
3. 输出 macOS 原生解密符号探测结果；符号存在绝不等于已具备账号授权。
4. macOS 原生 remap 实验入口，子进程隔离异常并设置 30 秒超时。
5. 只有原生调用成功且读取出的加密区内容发生变化时，才允许生成 **candidate**；仍不声明代码正确或可安装。

这是原型的单个 Mach-O 核心，不是完整 IPA 服务。暂不支持 FAT、ZIP 解包/重打包、应用下载、账号凭据初始化、支付或 TG 接入。

## GitHub 上查看验证

打开 Actions → Native engine feasibility。成功运行会生成各平台程序和 capability.json，保留 3 天。

- probe: 报告平台和原生符号是否存在。
- inspect: 只读解析二进制；cryptid=0 不是“解密已验证”。
- attempt: 实验性 macOS 路径，需要兼容运行环境和该应用的有效授权。

仓库不提供 IPA 上传或任意远程下载工作流。CI 全部使用合成样本，不登录 App Store。

## 技术限制与下一步

GitHub macOS 虚拟机不是已授权的 App Store 解密节点。编译成功、系统符号存在和原生 API 返回成功，都不能分别证明真实应用已解密。实际账号授权、系统版本与平台限制仍需可验证证据。

下一阶段必须先解决：在不依赖个人手机的环境中，如何取得并维持所需的授权和解密能力。没有证据前，不搭收费假流程、不将加密标记直接改零当作结果、不承诺任意应用可用。

收费服务还需要独立生产运行环境；当前“仅 GitHub 执行”的约束保持不变，未授权生产部署。

## 来源

实现代码为本项目编写。接口和格式依据：

- [Apple XNU mman.h](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/sys/mman.h)
- [Apple XNU Mach-O loader.h](https://github.com/apple-oss-distributions/xnu/blob/main/EXTERNAL_HEADERS/mach-o/loader.h)
- [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)

开源仓库或构建平台的使用权限不自动授予第三方应用的处理和分发权。

## 第二阶段：真实接口调用与 IPA 包检查

- Actions 在隔离子进程内对无授权、合成的 Mach-O 调用原生 remap；记录返回值、errno 和信号。调用设有 10 秒超时，临时文件随后删除。
- 无授权合成样本被拒绝是正常的，但不能由此断言“所有真实 IPA 都不能解密”。同样，符号存在或调用返回 0 也不证明真实应用已成功解密。
- tools/ipa_audit.py 直接读取 ZIP，不提取文件到磁盘。扫描主程序、扩展、框架和 FAT 内所有架构；支持 32/64 位 Mach-O，检查重复路径、路径穿越、符号链接及读取预算。
- 报告区分 encrypted_slices_present 与 no_encrypted_flags_found，两者均不声明 plaintext_verified 或 runtime_verified。
- 完整 IPA 的解密、重打包和真实应用授权初始化仍未实现。工具不会把原有 IPA 修改成“假砸壳包”。

## 第三阶段：原生调用对照

diagnose 命令分别以 cryptid=0、1、2 调用同一接口，每组都在独立子进程中执行，输出 native-controls.jsonl。0 是不加密控制组：即使返回成功也绝不代表 FairPlay 解密成功。1、2 分别检查应用及模型加密调用路径。所有样本仍无 Apple 授权，失败结果不能精确等同于“缺账号”。

## 真实 IPA 的手动诊断入口

Actions → Authorized IPA diagnostic，仅主分支可运行。将原始 IPA 的 HTTPS 直链保存到仓库 Actions Secret AUTHORIZED_IPA_URL。商店页面不是下载地址。当前目标为 examples/target.json 中的 App ID 6599842047。

流程不登录 App Store，不生成账号凭据。保留包内授权文件相对路径供原生系统尝试读取。IPA 和候选文件仅在临时目录处理，任务正常退出后删除，不上传文件，只输出不包含应用标识的计数摘要。即使生成候选，仍为 candidate_unverified。

此入口尚未验证真实 IPA，必须先有有效原始包来源。公开日志和摘要不输出地址、授权内容、候选明文。实际输入由 GitHub 托管运行器处理；不得将 Secret 理解为运行器之外的额外保密保证。
