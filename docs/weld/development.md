# Weld 开发指南

Weld 以 Brave Core 为上游维护自己的产品变更。项目关闭 Leo、钱包、Rewards、Brave Ads、VPN 和内置推广，保留 Shields、常规浏览、默认浏览器提示和必要通知。首次运行、权限、安全和更新提示的变更需要对应平台验收。

## 仓库与目录

| 路径 | 责任 |
| --- | --- |
| `src/brave` | Weld Git 工作区。上游 Brave Core 路径属于 GN、资源打包和同步接口。 |
| `src` | 由 gclient 管理的 Chromium 工作区及依赖。 |
| `src/brave/patches` | 可重放的 Chromium 补丁。 |
| `src/brave/chromium_src` | Brave 的 Chromium 覆盖入口。 |
| `src/brave/ci` | 固定版本、构建、验收、发布和上游检查工具。 |
| `src/brave/docs/weld` | Weld 维护文档。上游文档仍在 `docs/`。 |
| `src/out` | 生成文件和候选编译产物，按配置隔离。 |

以 `origin` 表示 Weld，以 `upstream` 表示 Brave Core。Chromium 由 `package.json` 选取版本，`ci/pins.json` 记录复核过的 Chromium SHA 和已合并的 Brave 提交。用补丁和覆盖目录提交 Chromium 变更，随后用空白工作区检查补丁重放。升级应同时更新这两份版本声明。

## 创建工作区

```sh
mkdir -p Weld/src
git clone --filter=blob:none https://github.com/Zolmid/Weld.git Weld/src/brave
cd Weld/src/brave
git remote add upstream https://github.com/brave/brave-core.git
git switch main
node --version
pnpm --version
python3 -B ci/check.py
```

从 `ci/pins.json` 安装固定 Node 和 pnpm。初次联网同步会下载 Chromium、平台工具链和依赖，需要 NTFS/APFS/ext4 等支持大文件和符号链接的本地盘。每台负责人机器宜预留 300 GiB，Windows 客户机首次完整同步和编译宜预留更多。大规模并行和符号表编译需要额外内存和空间。

| 目标 | 工具链和实际验证环境 |
| --- | --- |
| macOS arm64 | Apple Silicon、Xcode 27.1、macOS SDK 27 和 Metal Toolchain，带图形会话。 |
| iOS arm64 | Apple Silicon、Xcode 27.1、iOS SDK/Simulator 27.1 和固定 SwiftPM 解析结果。 |
| Linux x64 | Ubuntu x86-64，Chromium 的 `build/install-build-deps.sh`，Xvfb 与可用的 Chromium sandbox。 |
| Android arm64 | Linux x86-64 安装 Chromium Android build deps，验收用 ARM64 Android 16 模拟器，另外提供 `adb` 和 `apkanalyzer`。 |
| Windows x64 | 短路径 NTFS、Developer Mode、Git for Windows、Visual Studio 2026 C++ Desktop + x64 ATL/MFC、Windows SDK 10.0.28000.2270 及 x64 Debugging Tools。 |

Windows on Arm 可作为本地尝试。它还需要手动安装 x64 SDK Debuggers。验收 Windows x64 发布包时须使用可独立复现的目标平台环境。Linux/Android 默认使用原生 x86-64 构建机。本地 ARM 主机上的 x86 翻译环境可能需要 JVM 兼容调整，CI 目标使用上游原生工具链。

## 同步、构建和测试

在 `src/brave` 执行。首次使用 `pnpm run init`，后续使用 `pnpm run sync`。Linux 和 Android 可以先用 `--nohooks` 初始化 Git/DEPS，然后按固定 Chromium 版本的官方说明安装预依赖并执行正常同步。

```sh
pnpm run init --target_os=mac --target_arch=arm64 --no-history
pnpm run build Static --target_os=mac --target_arch=arm64 -C weld_mac_arm64 \
  --slim --skip_signing --gn=enable_updater:true --gn=enable_update_notifications:true
pnpm run test:scripts --runInBand
```

自动化入口为 `python3 -B ci/build.py PLATFORM OUTPUT`。支持 `linux`、`win`、`mac`、`ios`、`android`。目标目录使用新的路径。脚本会核对 chromium SHA 和 GN 生成开关，构建本平台包。桌面平台执行 Shields 单元测试与启动测试。iOS 启动模拟器应用并扫描设备包。Android 的 ARM64 APK 由单独模拟器 job 安装测试。Linux build runner 先准备系统依赖和 sandbox。Windows 启用 Developer Mode 并设置 `DEPOT_TOOLS_WIN_TOOLCHAIN=0`。

iOS 的内核和 Swift 客户端分别构建。 `ci/build.py` 将 `BRAVE_IOS_SLIM=1` 和 `BRAVE_IOS_PREBUILT_CORE_DIR` 传至 preaction 与 Xcode。模拟器用 `Debug (No Core)`。真机候选用 `Release (AppStore)` 且关闭签名。修改 entitlements，需一起检查应用、扩展、包内 Mach-O、插件与框架。真机部署使用单独的正式签名配置。

macOS 本地可执行 `bash .codex/run check`、`sync-apple` 和 `build-mac`。如果该主机的 IPv6 下载路径不稳定，`sync-apple` 有命令作用域内的 IPv4 兼容配置。正常网络可设 `BRAVE_FETCH_IPV4_ONLY=0`。使用 `DEVELOPER_DIR` 选择版本，按需安装 Xcode 平台与 Metal 工具链；保留系统默认 Xcode。

## 故障定位

1. **同步失败**。确认 checkout 成对存在，锁定版本匹配，Git 可访问 upstream 与 Chromium。保留同步输出和失败项目名。
2. **补丁失败**。在新建的试验 checkout 重放补丁，复核上游文件移动或签名变更，将修复更新回 `patches/`。保留当前构建和未提交改动。
3. **GN 失败**。先检查平台工具链和 `args.gn` 中的 `--slim` 结果。用 `siso query targets` 了解实际目标名称与依赖。
4. **包可编译但不会启动**。从隔离的新目录或新模拟器安装验收，检查动态库、资源、签名或启动参数。提交须附脚本和可重放证据。
5. **更新失败**。分别核对 Shields 规则组件更新和应用分发更新。规则已注册、界面有按钮、真实下载成功、已使用新规则是四种不同证据。

[CI 与发布](ci-release.md)提供运行记录及清理前验收要求。
