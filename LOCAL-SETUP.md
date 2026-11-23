# Brave 开发环境

准备日期：2026-11-04。目标为开发构建；签名、发布和设备验收另行处理。


## 已验证状态

| 项目 | 结果 |
|---|---|
| Brave/Chromium + macOS/iOS DEPS 初始化 | 官方同步命令退出 0；补丁和 runhooks 完成 |
| macOS arm64 GN 配置 | 生成 39,366 个 targets；直接 Siso 构建图查询退出 0 |
| macOS arm64 精简版 | 2026-11-16：Static 独立 App 构建完成。复制到构建目录外启动成功；本地页面、Shields 按站点拦截脚本和组件更新页面验证通过 |
| iOS Simulator arm64 GN 配置 | 生成 26,447 个 targets；直接 Siso 构建图查询退出 0 |
| iOS Simulator arm64 精简版 | 2026-11-15：精简 BraveCore 与完整 Client 构建成功；模拟器加载本地页面并执行脚本，也验证了 Shields 可以按站点阻止脚本 |
| iOS 真机 arm64 精简版 | 2026-11-16：未签名 `Release (AppStore)` 应用包构建完成。检查了 13 个 Mach-O 文件和 5 个扩展；未发现 VPN 实现、链接或插件，应用与扩展的签名配置也不请求 VPN 权限 |
| iOS bootstrap | JavaScript 资源、SPM framework 占位文件、LLDBInit 已生成；占位 framework 不是编译产物 |
| Xcode 27.1 Swift 依赖 | `-resolvePackageDependencies -onlyUsePackageVersionsFromResolvedFile` 退出 0；缓存位于 `.local/SourcePackages` |
| 正式签名 / 整包在线升级 | 未执行 |
| Windows / Linux / Android 主机 | 尚无已配置的 x64 构建主机，未远程验证 |
| Codex 本地项目登记 | 文件准备完成；需要用户在界面添加主文件夹和辅助文件夹 |

验证日志位于工作区 `.local/logs/`。构建图检查先经过上游构建包装器；当前 Siso 对旧 `ninja -t targets/list` 子命令返回 1，随后使用其支持的 `siso query targets` 分别查询两张构建图，均成功。没有据此宣称执行过编译。

## Codex 项目

在 Codex 新建本地项目 **Brave**，将以下文件夹设为主文件夹：

`/Users/zolmid/Project/Brave/src/brave`

将 `/Users/zolmid/Project/Brave` 添加为辅助文件夹，允许访问 Chromium、工具和构建产物。主文件夹必须是实际 `brave-core` Git 仓库，方便代码差异和 Git 操作。`brave-browser` 现在只保存发布、问题和 wiki，不作为源码项目。

- 默认使用 **Local** 模式。Chromium 是父级独立 Git 仓库；单独给 `brave-core` 创建 worktree 不会复制 Chromium、DEPS 或工具链。
- 为不同开发目标开独立聊天，保持同一文件只有一个写入者。
- 保留上游 `AGENTS.md` 和 `.claude/CLAUDE.md`；本文件记录本机配置。
- `.codex/environments/environment.toml` 提供检查、同步、macOS 构建、iOS Simulator core 构建和打开 Xcode 的动作。
- 自动 setup 只提示阅读本文件，不自动触发数十 GB 下载或编译。显式运行同步动作。
- 本机路径和工具配置不含凭据，新增项目配置保持可审查，尚未提交或推送。

## 目录与版本

```text
Brave/
  src/                       Chromium，由官方同步命令管理
    brave/                   brave-core，Codex 主文件夹
      .codex/                本地动作和下载兼容配置
      ios/brave-ios/          iOS Swift 工程
    out/                     编译产物，由上游工具命名
  tools/pnpm/                项目专用 pnpm 11.11.0
  .local/logs/                初始化日志
  vm-images/                 已下载的备用虚拟机安装介质
  artifacts/                 从编译主机取回的最终产物（按平台/架构/提交分目录）
```

- 初始上游分支：`master`，属于开发分支，不能称为稳定发行版。
- 初始提交：`ba97d276d3c122d3e57d5193a9cd59e233d34492`。
- 此提交 Brave `1.101.22`；Chromium `157.0.8103.30`，对应提交 `638dd0ef2fd334b657efb909d06d0164ea4d9443`（已核对官方 Git tag）。
- `package.json` 要求 Node `>=24.16.0 <25.0.0`、pnpm `>=11.11.0`；已安装项目专用 pnpm，不修改全局版本。
- 本机 M4 / 32 GB，Xcode 27.1，macOS SDK 27.0、iOS SDK 27.1、Swift 6.4。

## 本机 macOS / iOS

在主文件夹执行：

```sh
bash .codex/run check
bash .codex/run sync-apple
bash .codex/run build-mac
bash .codex/run build-ios
bash .codex/run open-ios
```

同步使用官方 `pnpm run init` / `sync`，目标为 `mac,ios` 与 `arm64`，`--no-history` 减少 Chromium 历史下载。macOS 与 iOS 共用源码，但构建输出由上游按目标隔离。`build-ios` 只构建模拟器的 BraveCore；完整 iOS 应用需在 `ios/brave-ios/App/Client.xcodeproj` 的 Debug scheme 中构建。

用 `bash .codex/run build-mac -C Component_arm64_slim --slim` 构建 macOS 开发版；该 App 依赖构建目录中的动态库。独立 App 用 `pnpm run build Static --target_os=mac --target_arch=arm64 -C Static_arm64_slim --slim --skip_signing --gn=enable_updater:true --gn=enable_update_notifications:true` 构建。`--slim` 关闭 Leo、本地 AI、钱包、Rewards、Brave Ads 和两代 VPN，保留 Shields。Metal 着色器依赖 Xcode Metal Toolchain。

Static App 内含 macOS 整包更新器。非官方开发包默认不运行整包自动更新；本地验证只检查了 Shields 组件已注册且组件页面有检查更新的入口。记录见 `.local/logs/smoke-mac-static-slim.log`。

iOS 先执行 `bash .codex/run build-ios -C ios_Debug_arm64_simulator_slim --slim`。然后在启动 Xcode 前选中该内核：

```sh
export BRAVE_IOS_SLIM=1 BRAVE_IOS_PREBUILT_CORE_DIR=ios_Debug_arm64_simulator_slim
python3 ios/brave-ios/scripts/scheme_preaction.py --configuration Debug --platform_name iphonesimulator --only_update_symlink
```

构建 `Debug (No Core)` scheme 时将这两个变量同时传为 Xcode 构建设置，模拟器架构用 `ARCHS=arm64`。模拟器包使用本地签名；日志见 `.local/logs/build-ios-client-full-slim.log` 和 `.local/logs/smoke-ios-client-full-slim.log`。

真机可用 `pnpm run build Release --target_os=ios --target_arch=arm64 --target_environment=device -C ios_Release_arm64_device_slim --slim --skip_signing --gn=is_official_build:false` 构建内核。把 `BRAVE_IOS_PREBUILT_CORE_DIR` 换成 `ios_Release_arm64_device_slim`，用相同脚本以 `--configuration Release --platform_name iphoneos --only_update_symlink` 选中内核，再用 `Release (AppStore)` scheme 和 `CODE_SIGNING_ALLOWED=NO` 构建。验收日志见 `.local/logs/check-ios-client-device-slim.log`。未签名的本地产物不能安装到真机；iOS 应用更新沿用 App Store 分发，Shields 等浏览器组件使用原有的组件更新服务。

启动脚本只在当前子进程清除失效的 `SDKROOT`，通过现有 `xcode-select` 选择 Xcode。没有全局切换或降级 Xcode。旧 iOS wiki 写的是 Xcode 26.0；本次源码已要求 Swift >=6.2.1，且固定 Chromium 的 macOS SDK 配置为 27.0。以实际固定源码和构建结果确认兼容性，不能仅根据旧 wiki 宣称需要降级。

本机访问 Google 下载地址时出现 IPv6 `SYN_SENT` 长时间等待。同步动作默认启用 `.codex/ipv4/sitecustomize.py`，只让该命令及其 Python 子进程在未指定地址族时使用 IPv4。HTTPS 证书和下载完整性校验保持开启，不改变系统网络或代理。网络恢复后可执行：

```sh
BRAVE_FETCH_IPV4_ONLY=0 bash .codex/run sync-apple
```

日志：`/Users/zolmid/Project/Brave/.local/logs/init-mac-ios.log`。初始化下载完成、GN 配置成功、编译成功、程序启动成功是不同状态。

## Windows / Linux / Android：优先临时编译服务器

用户已选择优先临时服务器，UTM 仅作为备选。本轮没有购买服务器、创建账户、生成密钥或上传代码。

| 目标 | 构建主机 | 必要条件 |
|---|---|---|
| Windows x64 / arm64 | Windows x64 | Windows 10+，NTFS，Visual Studio 2026 >=18.0.0，C++ Desktop + ATL/MFC；arm64 目标增加 ARM64 tools/MFC |
| Linux x64 | Linux x86_64 | Git、Python、Node 24、pnpm >=11.11；按固定 Chromium 的 Linux 文档安装 build-deps |
| Android arm64 | Ubuntu 24.04 x86_64 | Git、Python、Node 24、pnpm >=11.11；运行该 Chromium 提交的 Android build-deps 安装脚本 |

固定 Chromium 文档要求 Windows SDK **10.0.28000.2270**、Debugging Tools **10.0.26100.3323+**。Windows 在短路径 `C:\brave\src\brave` 编译，启用 Developer Mode 以满足上游符号链接检查；服务器选型时优先选择符合该文档的系统，不能默认所有 Windows Server 版本都已验证。

资源建议是首次构建的规划值：每台 8–16 vCPU、32–64 GB RAM、至少 300 GB SSD；上游最低磁盘 100 GB，实际空间随目标和调试符号变化。先验证一个目标，再扩大并发。缓存应保留在持久盘，临时计算实例关机前取回构建产物。

所有主机先使用同一 Brave 提交。下列命令在已经安装基础工具的主机上执行；这里没有远程执行它们。

Windows PowerShell：

```powershell
git clone --filter=blob:none https://github.com/brave/brave-core.git C:\brave\src\brave
Set-Location C:\brave\src\brave
git checkout ba97d276d3c122d3e57d5193a9cd59e233d34492
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = '0'
pnpm run init --target_os=win --target_arch=x64 --no-history
pnpm run build Component --target_os=win --target_arch=x64 -C win_Component_x64_slim --slim
```

Android / Ubuntu：

```sh
git clone --filter=blob:none https://github.com/brave/brave-core.git "$HOME/brave/src/brave"
cd "$HOME/brave/src/brave"
git checkout ba97d276d3c122d3e57d5193a9cd59e233d34492
pnpm run init --target_os=android --target_arch=arm64 --no-history --nohooks
sudo ../build/install-build-deps.sh --android
pnpm run sync --target_os=android --target_arch=arm64 --no-history
pnpm run build Static --target_os=android --target_arch=arm64 -C android_Static_arm64_slim --slim
```

Linux x64：在固定版本的独立 Linux checkout 初始化 `linux` 和 `x64`，安装该 Chromium 提交的 Linux build-deps，再执行 `pnpm run build Component --target_os=linux --target_arch=x64 -C linux_Component_x64_slim --slim`。`--slim` 只设置原生 GN 开关；Android / iOS 还需验证各自的应用打包结果。

首次配置服务器时，需先确定供应商、区域、预算、机器类型和现有连接方式。不要把密码、SSH 私钥、Android keystore 或 Apple 签名材料加入 Git、项目说明或聊天。源码修改在用户授权的仓库或补丁渠道传输；编译产物按平台、架构、Brave SHA 和 Chromium版本归档到 `artifacts/`。

## UTM 备选

- Windows 11 ARM64 可用硬件虚拟化，但 Chromium 文档还要求补齐 x64 Debuggers。
- Android 官方要求 Linux x86_64。M4 上全系统 x86_64 模拟代价很高；ARM Linux + Rosetta 没有通过本项目构建验证。
- Ubuntu 24.04.5 Server amd64 ISO 已从 Ubuntu 官方站下载，SHA-256：`97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8`。
- 本次 UTM 仅进入了创建向导，没有保存虚拟机或安装来宾系统；不算可用构建主机。

## 官方依据

- https://github.com/brave/brave-core/blob/master/README.md
- https://github.com/brave/brave-browser/wiki/iOS-Development-Environment
- https://chromium.googlesource.com/chromium/src/+/refs/tags/157.0.8103.30/docs/windows_build_instructions.md
- https://chromium.googlesource.com/chromium/src/+/refs/tags/157.0.8103.30/docs/android_build_instructions.md
- https://learn.chatgpt.com/codex/projects
- https://learn.chatgpt.com/docs/environments/local-environment
- https://learn.chatgpt.com/docs/agent-configuration/agents-md
