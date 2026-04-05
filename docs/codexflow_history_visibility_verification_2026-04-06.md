# CodexFlow 历史可见性补丁验证记录（2026-04-06）

## 1. 验证范围与环境

- Worktree: `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility`
- Branch: `feat/codexflow-history-visibility`
- Install root: `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked`
- Launch cmd: `C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd`
- Codex home: `C:\Users\17795\.codex`
- CodexFlow userData: `C:\Users\17795\.codexia`
- Launch log: `C:\Users\17795\AppData\Local\CodexFlow\launch.log`
- 当前 selected workspace（来自 `C:\Users\17795\.codexia\settings.json`）: `\\?\C:\Users\17795\Desktop`
- 初始备份状态：执行前未发现 `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-*`

## 2. 执行命令

### 2.1 仓库内自动化验证

```powershell
node --test .\scripts\codexflow\tests\*.test.cjs
```

### 2.2 真实补丁执行

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\codexflow\apply-history-visibility-patch.ps1 -InstallRoot 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked' -LaunchCmd 'C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd'
```

### 2.3 启动日志检查

```powershell
Get-Content 'C:\Users\17795\AppData\Local\CodexFlow\launch.log' -Tail 50
```

### 2.4 运行后产物/状态补充检查

```powershell
Get-ChildItem -LiteralPath 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources' -Filter 'app.asar.bak-*'
Get-FileHash 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar','C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430','C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar'
Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue
```

### 2.5 用真实旧会话样本回放 helper 行为

```powershell
node - <scripts omitted in doc; see execution log below>
```

> 说明：由于当前执行环境无法直接自动化 Electron GUI 点击，我额外用补丁产物里的 `historyVisibility.cjs` 对真实 `C:\Users\17795\.codex\sessions\*.jsonl` 做了 helper 级回放，作为 UI 结果的替代证据。

## 3. 预期结果

- `resources\app.asar.bak-*` 已生成
- 首次重启后 CodexFlow 重新索引 Codex 历史
- 当前 workspace 仍为 `C:\Users\17795\Desktop` 时，历史列表不再空白
- 能看到带 `[cliproxyapi · ...]` / `[cpa_legacy · ...]` / `[openai · ...]` 前缀的旧会话
- 项目内命中存在时仍优先显示项目内历史

## 4. 回滚命令

```powershell
Copy-Item -LiteralPath 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430' -Destination 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar' -Force
```

## 5. 实际执行记录

### 5.1 自动化验证结果

执行：

```powershell
node --test .\scripts\codexflow\tests\*.test.cjs
```

结果：`pass 16 / fail 0`

新增/修正的安装版兼容回归覆盖了以下真实差异：

- `indexer.js` 中 `rs.on('end')` / `rs.on('error')` 分支多出 `dirKey` 赋值
- `indexer.js` 中重扫 summary 存在 `providerId` 变量版与 `providerId: "codex"` 字面量版两种形态
- `main.js` 中 `history.list` 返回块缩进层级比测试夹具更深

### 5.2 真实补丁执行结果

首次真实执行时，安装版源码与测试夹具存在锚点差异，先后命中以下错误：

1. `Missing patch anchor: indexer.details.resolve.end`
2. `Missing patch anchor: indexer.rescan.summary`
3. `Missing patch anchor: main.history.list`

上述问题均已在仓库内通过最小兼容修复解决，并补了对应回归测试。修复后再次执行真实补丁，成功输出：

```text
EXTRACT_ROOT=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app
BACKUP_CREATED=C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430
PATCHED_ASAR=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar
LAUNCH_STARTED=C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd
```

补丁后产物校验：

- 新备份文件：`C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430`
- 当前安装版 `app.asar` SHA-256：`E36A06C382FCA2F470294A65FD23241234105EA62DDCEF88F0B2F2850B51BA12`
- `C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar` SHA-256：`E36A06C382FCA2F470294A65FD23241234105EA62DDCEF88F0B2F2850B51BA12`
- 备份 `app.asar.bak-20260406042430` SHA-256：`42287497EFB8ACACBFC25A4EDE045EEAE82DDE8F4841C8DEFC8C70229DA1CAD2`

结论：安装目录中的 `resources\app.asar` 已被 patched 版本替换，且原始版本已备份。

### 5.3 启动日志与进程观察

`C:\Users\17795\AppData\Local\CodexFlow\launch.log` 尾部包含本次重启记录：

- `==== [2026/04/06 ... 4:24:32.00] launch request ====`
- `CODEXFLOW_CODEX_BIN=C:\Users\17795\.local\bin\codex.exe`

`Get-Process -Name 'CodexFlow'` 显示 4 个 `CodexFlow.exe` 进程于 `2026/04/06 04:24:33` 启动，路径均为：

- `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\CodexFlow.exe`

同时，`C:\Users\17795\.codexia\settings.json` 在补丁执行后仍保持：

- `workspace.cwd = \\?\C:\Users\17795\Desktop`
- `workspace.projects = ["\\\\?\\C:\\Users\\17795\\Desktop"]`

### 5.4 已落到安装产物的关键代码证据

来自 `C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app\dist\electron\main.js`：

- `const { selectHistorySessions } = require("./historyVisibility.cjs");`
- `const selection = selectHistorySessions({ filtered: sorted, all, offset, limit });`
- map 结果已包含：`subProvider`、`cwd`、`fallbackReason`

来自 `C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app\dist\electron\indexer.js`：

- `return historyVisibility.buildIndexedCodexSummary(...)`
- `resolve(historyVisibility.buildIndexedCodexDetails(...))`
- 重扫 summary 已注入：`subProvider`、`source`、`originator`、`cwd`

## 6. 人工 UI 复核清单

1. 保持 selected workspace 为 `C:\Users\17795\Desktop` 不变。
2. 打开 CodexFlow 历史列表，确认不再空白。
3. 至少看到一条 `[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] ...`。
4. 至少看到一条 `[openai · ...] ...` 或 `[cliproxyapi · ...] ...`。
5. 切回 `D:\codex\kaoyan-miniapp-mvp` 对应项目后，项目内历史优先，不应总是落到 fallback。

## 7. 证据分层

### 7.1 可直接自动化验证的事实

1. **补丁脚本已在真实安装目录成功执行**
   - 直接证据：`BACKUP_CREATED=...app.asar.bak-20260406042430`
   - 直接证据：`PATCHED_ASAR=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar`
   - 直接证据：安装版 `app.asar` 与 `app.patched.asar` 哈希一致，且与备份哈希不同

2. **CodexFlow 已被真实重启，且 selected workspace 未被改动**
   - 直接证据：`launch.log` 中 `2026/04/06 04:24:32` 的 launch request
   - 直接证据：4 个 `CodexFlow.exe` 进程于 `2026/04/06 04:24:33` 启动
   - 直接证据：`C:\Users\17795\.codexia\settings.json` 仍是 `\\?\C:\Users\17795\Desktop`

3. **安装产物已包含 fallback / 前缀所需运行时代码**
   - 直接证据：patched `main.js` 已引入 `selectHistorySessions`，返回结构含 `subProvider/cwd/fallbackReason`
   - 直接证据：patched `indexer.js` 已引入 `buildIndexedCodexSummary/buildIndexedCodexDetails`

4. **真实旧会话元数据中确实存在需要展示的 provider/cwd 组合**
   - 直接证据：对真实 `C:\Users\17795\.codex\sessions\*.jsonl` 解析后，统计得到：
     - `cliproxyapi`: `99`
     - `openai`: `54`
     - `cpa_legacy`: `19`
   - 直接证据：helper 回放可生成以下真实前缀样例：
     - `[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] sample preview`
     - `[openai · D:\codex] sample preview`
     - `[cliproxyapi · D:\codex\zc] sample preview`

5. **helper 级回放已验证 fallback / 项目优先语义**
   - 直接证据：基于真实会话样本运行 `selectHistorySessions(...)` 得到：
     - `desktopFiltered = 0`
     - `desktopMode = "fallback"`
     - `desktopPreview0 = "[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] sample preview"`
     - `projectFiltered = 53`
     - `projectMode = "project"`
     - `projectPreview0 = "[openai · D:\codex\kaoyan-miniapp-mvp] sample preview"`

### 7.2 仍需人工点击 UI 复核的项

1. **“当前 workspace 为 Desktop 时，历史列表不再空白”**
   - 当前没有直接 Electron UI 自动化能力；未直接点击列表确认。

2. **“能在 CodexFlow 历史面板里看到 `[cpa_legacy · ...]` / `[openai · ...]` / `[cliproxyapi · ...]` 条目”**
   - 已通过 helper + 真实会话元数据证明前缀可生成、原始数据存在，但未直接拍到 GUI 列表。

3. **“首次重启后 CodexFlow 重新索引 Codex 历史”**
   - 本次未拿到 GUI 内部索引进度条或列表刷新截图。
   - 额外检查 `C:\Users\17795\.codexia\data.db` 的 `sessions` 表时，记录数仍为 `0`；这不足以证明“未索引”，更可能说明该表并非开机立刻写入或仍需进入历史面板触发。故此项仍待人工 UI 复核。

4. **“切回 `D:\codex\kaoyan-miniapp-mvp` 后项目内历史优先，不总是落到 fallback”**
   - helper 级回放已证明真实样本下 `projectMode = "project"`，但最终 GUI 呈现仍需人工切换项目再确认一次。

## 8. 本次顺带修复的脚本兼容问题

为完成真实安装验证，补了安装版兼容性小修，并已通过回归测试：

- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\lib\patchInstalledFiles.cjs`
- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\codexflow-patch.test.cjs`
- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\fixtures\electron\indexer.installed.before.js`
- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\fixtures\electron\main.installed.before.js`

修复目标仅限：让补丁脚本兼容本机安装版 `app.asar` 的真实源码形态，不改变补丁意图。
