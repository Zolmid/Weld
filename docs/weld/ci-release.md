# Weld CI 与发布

## 检查分层

| Workflow | 启动 | 完成条件 |
| --- | --- | --- |
| Weld checks | PR、main 推送、候选构建复用 | 源码版本、开关、补丁语法、Python、TypeScript、ESLint、构建脚本测试。 |
| Weld platform candidates | main 上手动启动 | 五个平台的候选包来自同一 Weld SHA 和 Chromium SHA。桌面浏览测试和 Shields 测试通过。iOS 模拟器与无 VPN 扫描通过。Android APK 在 ARM64 模拟器安装、运行并通过 Shields 测试。 |
| Weld release draft | main 上手动选择候选 run ID 和版本 | 同一成功候选 run 的五个包经独立签名/检验任务验证，确认 SHA-256 和来源后生成草稿。 |
| Weld upstream and security watch | 定时或手动 | 官方 Brave 固定版本和 Chromium 稳定渠道版本的差异报告。 |

公共 PR 使用 GitHub 托管 runner。昂贵的 Chromium 编译使用仅注册给本仓库的隔离 runner。候选构建完成后重新下载产物才进入签名。签名、通知和发布权限由环境约束。

## Runner 准备

普通 GitHub 托管镜像的磁盘和时间需与 Chromium 的实际需求分别核验。常用初始规格为 16 vCPU、32–64 GiB 内存、300–500 GiB SSD。对于第一轮 Windows 和 iOS 全编译，需按测量结果扩容。保留包缓存可以复用，但每个 job 使用独立 checkout 和临时产物目录。编译与签名隔离，签名 runner 不承接 PR。

| 标签 | 工作 |
| --- | --- |
| `weld-linux-x64` | Linux GUI/sandbox 测试，Android arm64 构建。 |
| `weld-windows-x64` | Visual Studio/SDK、x64 原生运行，支持 Python 3 和 Git Bash。 |
| `weld-macos-arm64` | macOS arm64 构建、图形启动。 |
| `weld-ios-arm64` | iOS Device 与 Simulator，已启动或可启动的隔离 Simulator。 |
| `weld-android-arm64-emulator` | Android arm64 ARM64 API 36 安装运行，英文界面和一次性测试环境。 |
| `weld-release-linux`、`weld-release-windows`、`weld-release-macos`、`weld-release-ios`、`weld-release-android` | 校验、签名、封装，具备本平台验证工具。 |

开发环境变量使用 `weld-build`，包含 `WELD_IOS_SIMULATOR_UDID` 和 `WELD_ANDROID_SERIAL`。使用独立的 job 专用模拟器，确保没有个人资料与登录状态。各签名环境使用 `weld-signing-linux`、`weld-signing-win`、`weld-signing-mac`、`weld-signing-ios`、`weld-signing-android`。 `weld-release` 控制草稿生成。环境仅允许 `main`，设置审批人并配置团队审批制度。Signing runner 的签名钥匙只能由签名环境可用，且要限制到单独 OS 账户。安装 runner 或购买容量前先审批成本与使用范围。

## 签名与包契约

候选阶段仍沿用上游的开发包布局与平台 ID。正式分发需配置由 Weld 控制的应用标识、签名证书、更新地址和商店记录。版本号、标识和签名主体在发布线内保持稳定。GitHub workflow 环境变量 `WELD_RELEASE_DRIVER` 指向签名主机中受限的、已审查的绝对路径。调用入参依次为平台、候选包路径、输出路径和 Weld 版本。密钥从 Keychain、系统证书存储、硬件签名器或受保护的配置读入。

| 平台 | 输出与验收 |
| --- | --- |
| Linux | `.tar.gz` 可运行包。含沙箱、资源、区域包和许可。GUI 浏览、脚本拦截与恢复通过。 |
| Windows | Authenticode 签名的 x64 可运行 ZIP。签名和时间戳通过 `signtool` 验证，从解包目录运行浏览与 Shields 检查。 |
| macOS | Developer ID 签名和 notarize 后的 arm64 DMG。验证 ticket、Gatekeeper 和映像。验收前从独立 macOS 用户安装并运行。 |
| iOS | 配置 Weld-owned Bundle ID 的签名 IPA。由有权主体执行 Xcode archive/export，核验主程序和扩展的签名及 provisioning。下载 IPA 后再次扫描无 VPN 并通过 TestFlight 或授权设备验收。 |
| Android | 使用 Weld-owned 应用 ID 以及发布密钥签名的 arm64 APK。APK 签名校验与模拟器测试针对签名产物执行。需要 Play Store 时，在同一源码和签名配置下上传经 Play 验证的 AAB。 |

Apple 密钥不可同时出现在 build runner 和签名 runner。macOS 归档复制用 `ditto` 保留 bundle 结构。Windows 把签名和时间戳应用到自己的发布二进制，保留第三方签名。Android 对齐 APK 后再签名，并核对应用 ID、ABI、页尺寸兼容性和签名证书。

## 发布执行

1. 在可信分支合并受审查的变更。记录 Weld SHA、Brave 合并提交、Chromium SHA、上游安全公告和兼容范围。
2. 对 main 的准确 SHA 运行候选构建，下载五种产物及日志，验证目标操作系统。更新流程修改要额外验证从上一 Weld 版本升级、用户配置保留、Shields 规则更新与回滚。
3. 用该候选 run ID 和新的语义版本启动 Release Draft。workflow 校验候选所属仓库、workflow 名、提交、五个包与 SHA-256，并在 Chromium 固定版本落后于稳定渠道时停止。签名许可及批准完成后只生成 GitHub Release 草稿。
4. Maintainer 根据草稿和平台验收记录确认正式发布。iOS 由 App Store Connect/TestFlight 分发，Android 商店渠道另行验收。保留上一签名包、上一 tag、日志和新旧版本的兼容记录。
5. 发布后在新用户或模拟器重复启动、浏览与 Shields 测试，核对下载链接和签名。异常时停止新渠道，保留可审计的已发布记录，并按上一版本恢复服务。

## 本地编译环境清理的验收条件

至少有一次同一提交对应的 GitHub Actions 五平台签名包可下载、哈希匹配、可以安装或正常启动。Linux 需使用实际 sandbox，Windows 要完成真实 GUI，Android 需在模拟器安装并通过 Shields，iOS 需核查真机包无 VPN 并验证可分发签名，macOS 需核查签名与公证。完成云端重跑或按记录验证可复现后，才清理本地 Weld 构建缓存、任务专用容器/虚拟机和中间编译目录。已验收的发布包、源码、签名材料和用户数据按各自归档方式保留。

[GitHub 托管 runner 规格](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
