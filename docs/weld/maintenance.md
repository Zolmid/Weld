# Weld 维护与 PR 流程

## 日常 PR

1. 从最新 `main` 创建短生命周期的 `codex/描述` 分支。一个 PR 解决一个可独立验收的问题，先用 Draft 共享进行中的工作。
2. 填写改动动机、用户影响、平台、测试范围和回滚路径。提交使用可追溯的 GitHub 身份。避免把账号令牌、签名材料、编译输出和用户数据加入 Git。
3. GitHub 的 `Source checks` 为必需检查。浏览器、构建或签名路径变更须提供相应平台验收。关键安全与发布变更需独立审查。维护者解决所有 review 对话后合并。
4. 普通功能分支用 squash merge 整理历史。上游同步 PR 用 merge commit 保留祖先关系。主分支禁止 force-push 与删除，合并后清理已合并分支。
5. 每次发布都记录 PR 列表、上游版本和构建 run。发现回归时优先提交可审查的 revert，发布恢复包，保留变更记录。

推荐保护 `main`，要求通过 PR、通过状态检查、解决所有 review 对话及有效分支。单维护者期间可先保留必需检查，增加维护者后启用至少一位独立审批。Workflow 和 `ci/` 修改参与维护者审查，执行权限始终用最小范围。

## 定期吸收 Brave 更新

定时 workflow 读取官方项目并记录差异。它不推送代码。由维护者使用自身 GitHub 身份下载报告并准备上游 PR。

```sh
python3 -B ci/upstream.py report /tmp/weld-upstream.json
python3 -B ci/upstream.py prepare <已审查的-Brave-提交-SHA>
```

先审查 Brave 源码与 DEPS、平台 SDK 变更、许可证、工作流或脚本变更。 `prepare` 验证会合并的提交曾经经过报告检查，创建分支并尝试 merge，在出现冲突或受到 CI 改动时停止。处理冲突后复核 `ci/pins.json` 中 Brave/Chromium 的 SHA，和 `package.json` 的 Chromium tag，使用官方 tag 解引用结果。重新应用 Weld 补丁并验证精简开关。上游同步的最终合并保留 Brave 父提交，日后可用 ancestry 来追踪。

## Chromium 安全更新

- 每天看 Chromium Dash 的桌面及 Android Stable 版本与 [Chrome Releases 官方公告](https://chromereleases.googleblog.com/)。版本差异表示值得比较，安全覆盖以公告、Chromium tag 和实际修补提交为准。iOS WebKit 的安全覆盖另外跟踪 Apple SDK/系统；Weld 的 iOS Chromium 依赖也应同步和验收。
- 有 Brave 版本已经吸收安全修复时，优先合并官方 Brave 修订，保存覆盖 CVE 与各平台 tag 的证据。
- Brave 上游尚未吸收已利用或高危修复时，开专用安全 PR。核对适用的平台稳定版本和官方 Chromium tag 的 SHA，调研 Brave 的兼容前置改动，使用相同主版本的官方分支修复或已审查的安全更新。确认所有依赖、补丁、工具链和签名任务通过之后再部署。
- 安全 PR 先完成规则/脚本检查，重放补丁，运行五平台构建与功能测试，形成精确 SHA 的候选。记录影响范围、跳过理由、外部公告和升级/回退路径。发布节奏可以加急；签名、来源校验和安装验收仍是必需门槛。
- 通知失败负责维护者。定时报告为空、源站错误、超过预计时限、出现冲突或验证失败时，按失败原因排查；未验证的版本不进入签名与发布草稿。

## 分发更新

Weld 自己维护 GitHub 发布记录和版本号。正式升级需配置 Weld 自有的身份与更新渠道，避免安装覆盖 Brave 或跳回上游渠道。Shields 的规则数据来源由 Chromium/Brave 组件更新路径提供，验证新规则实际下载并能作用于既有配置。测试本地升级后，保留前一版签名包，在发布异常时恢复到已知正常版本。
