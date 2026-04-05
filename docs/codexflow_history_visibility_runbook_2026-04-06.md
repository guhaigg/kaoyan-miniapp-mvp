# CodexFlow 历史可见性补丁运行手册（2026-04-06）

## 1. 前置条件

- 操作系统：Windows（PowerShell 可用）。
- 已安装 Node.js 与 npm。
- 已存在安装目录（默认）：
  - `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked`
- 已存在启动命令（默认）：
  - `C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd`
- 已拉取本仓库并包含以下文件：
  - `scripts/codexflow/lib/historyVisibility.cjs`
  - `scripts/codexflow/lib/patchInstalledFiles.cjs`

> 说明：所有脚本都支持通过参数覆盖默认路径（`-InstallRoot` / `-LaunchCmd` / `-WorkRoot`）。

## 2. Dry-run（仅打印计划，不落盘）

在仓库根目录执行：

```powershell
npm run codexflow:history:patch:dry
```

期望输出包含：

- `DRYRUN extract => npm exec --yes --package @electron/asar -- asar extract ...`
- `DRYRUN patch => node ...\patchInstalledFiles.cjs --extract-root ... --helper-source ...`
- `DRYRUN pack => npm exec --yes --package @electron/asar -- asar pack ...`

Dry-run 不会：

- 解包/打包 asar
- 覆盖安装目录下 `app.asar`
- 启停 CodexFlow 进程

### 2.1 覆盖路径示例

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\codexflow\apply-history-visibility-patch.ps1 `
  -InstallRoot "D:\apps\CodexFlow\win-unpacked" `
  -LaunchCmd "D:\apps\CodexFlow\launch-codexflow.cmd" `
  -WorkRoot "D:\tmp\codexflow-history-visibility" `
  -DryRun
```

## 3. 正式执行

在仓库根目录执行：

```powershell
npm run codexflow:history:patch
```

执行链路：

1. 停止 `CodexFlow` 进程（若存在）
2. 解包 `resources\app.asar` 到工作目录 `app`
3. 执行 Node patch（注入 `historyVisibility.cjs` 并改写目标文件）
4. 重新打包为 `app.patched.asar`
5. 备份原始 `resources\app.asar` 为 `app.asar.bak-<timestamp>`
6. 用 patched asar 覆盖安装目录 `resources\app.asar`
7. 若 `LaunchCmd` 存在，自动拉起 CodexFlow

关键信息输出：

- `BACKUP_CREATED=...`
- `PATCHED_ASAR=...`
- `LAUNCH_STARTED=...`（若已启动）

## 4. 回滚

1. 关闭 CodexFlow（若正在运行）。
2. 在安装目录 `resources` 下找到最新备份：
   - `app.asar.bak-<timestamp>`
3. 将其覆盖回 `app.asar`：

```powershell
Copy-Item -LiteralPath "<InstallRoot>\resources\app.asar.bak-<timestamp>" -Destination "<InstallRoot>\resources\app.asar" -Force
```

4. 重新启动 CodexFlow，确认行为恢复。

## 5. 常见问题

- `InstallRoot not found`：安装目录路径错误，请传入正确 `-InstallRoot`。
- `app.asar not found`：目标安装可能不是该版本或结构不同。
- `Patch step failed`：检查 `scripts/codexflow/lib/*.cjs` 是否齐全且未损坏。
