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
- 关键基线备份：`C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430`

## 2. 执行命令

### 2.1 仓库内自动化验证

```powershell
node --test .\scripts\codexflow\tests\*.test.cjs
```

### 2.2 纠正性重打补丁前恢复原始基线

```powershell
$backup='C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430'
$asar='C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar'
Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Copy-Item -LiteralPath $backup -Destination $asar -Force
Write-Host "RESTORED_BASELINE_FROM=$backup"
Get-FileHash $backup,$asar
```

### 2.3 修正后真实补丁执行

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\codexflow\apply-history-visibility-patch.ps1 -InstallRoot 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked' -LaunchCmd 'C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd'
```

### 2.4 启动日志与运行状态检查

```powershell
Get-Content 'C:\Users\17795\AppData\Local\CodexFlow\launch.log' -Tail 50
Get-Process -Name 'CodexFlow' -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,Path
@"
import json
with open(r'C:\Users\17795\.codexia\settings.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(data['workspace']['cwd'])
print(data['workspace']['projects'])
"@ | python -
```

### 2.5 运行后产物与哈希检查

```powershell
Get-ChildItem -LiteralPath 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources' -Filter 'app.asar.bak-*' | Sort-Object LastWriteTime -Descending
Get-FileHash 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar','C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430','C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406044547','C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar'
```

### 2.6 helper 回放：统计 provider 数量与前缀样例

```powershell
@"
const fs = require('node:fs');
const path = require('node:path');
const root = 'C:/Users/17795/.codex/sessions';
const helper = require('C:/Users/17795/AppData/Local/Temp/codexflow-history-visibility/app/dist/electron/historyVisibility.cjs');

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.isFile() && full.endsWith('.jsonl')) yield full;
  }
}

const rows = [];
for (const file of walk(root)) {
  const first = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(Boolean);
  if (!first) continue;
  let obj;
  try { obj = JSON.parse(first); } catch { continue; }
  if (obj.type !== 'session_meta') continue;
  const payload = obj.payload || {};
  const subProvider = payload.model_provider || '';
  const cwd = payload.cwd || '';
  if (!subProvider || !cwd) continue;
  const summary = helper.buildIndexedCodexSummary({
    providerId: 'codex',
    id: payload.id,
    title: path.basename(file),
    date: new Date(payload.timestamp || obj.timestamp || Date.now()).getTime(),
    filePath: file,
    rawDate: payload.timestamp || obj.timestamp,
    dirKey: 'dummy',
    preview: 'sample preview',
    cwd,
    subProvider,
    source: payload.source,
    originator: payload.originator,
  });
  rows.push({ file, cwd, subProvider, preview: summary.preview });
}

const counts = {};
for (const row of rows) counts[row.subProvider] = (counts[row.subProvider] || 0) + 1;
console.log('provider_counts=' + JSON.stringify(counts, null, 2));
for (const [provider, cwd] of [
  ['cpa_legacy', 'D:\\codex\\kaoyan-miniapp-mvp'],
  ['openai', null],
  ['cliproxyapi', null],
]) {
  const found = rows.find((row) => row.subProvider === provider && (!cwd || row.cwd === cwd));
  console.log(provider + '_sample=' + JSON.stringify(found || null));
}
"@ | node -
```

### 2.7 helper 回放：验证 fallback / project 优先逻辑

```powershell
@"
const fs = require('node:fs');
const path = require('node:path');
const root = 'C:/Users/17795/.codex/sessions';
const helper = require('C:/Users/17795/AppData/Local/Temp/codexflow-history-visibility/app/dist/electron/historyVisibility.cjs');

function* walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (entry.isFile() && full.endsWith('.jsonl')) yield full;
  }
}

const all = [];
for (const file of walk(root)) {
  const first = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(Boolean);
  if (!first) continue;
  let obj;
  try { obj = JSON.parse(first); } catch { continue; }
  if (obj.type !== 'session_meta') continue;
  const payload = obj.payload || {};
  const subProvider = payload.model_provider || '';
  const cwd = payload.cwd || '';
  if (!subProvider || !cwd) continue;
  all.push(helper.buildIndexedCodexSummary({
    providerId: 'codex',
    id: payload.id,
    title: path.basename(file),
    date: new Date(payload.timestamp || obj.timestamp || Date.now()).getTime(),
    filePath: file,
    rawDate: payload.timestamp || obj.timestamp,
    dirKey: cwd.toLowerCase(),
    preview: 'sample preview',
    cwd,
    subProvider,
    source: payload.source,
    originator: payload.originator,
  }));
}

const projectCwd = 'D:\\codex\\kaoyan-miniapp-mvp';
const filteredProject = all.filter((row) => row.cwd === projectCwd);
const desktopFiltered = all.filter((row) => row.cwd === 'C:\\Users\\17795\\Desktop');
const desktopSelection = helper.selectHistorySessions({ filtered: desktopFiltered, all, offset: 0, limit: 3 });
const projectSelection = helper.selectHistorySessions({ filtered: filteredProject, all, offset: 0, limit: 3 });
console.log(JSON.stringify({
  total: all.length,
  desktopFiltered: desktopFiltered.length,
  desktopMode: desktopSelection.mode,
  desktopPreview0: desktopSelection.sessions[0]?.preview,
  projectFiltered: filteredProject.length,
  projectMode: projectSelection.mode,
  projectPreview0: projectSelection.sessions[0]?.preview,
}, null, 2));
"@ | node -
```

### 2.8 installed generic summary 路径：验证 non-codex provider 不被误改

```powershell
@"
const fs = require('node:fs');
const vm = require('node:vm');
const { patchIndexerSource } = require('./scripts/codexflow/lib/patchInstalledFiles.cjs');
const source = fs.readFileSync('./scripts/codexflow/tests/fixtures/electron/indexer.installed.before.js', 'utf8');
const patched = patchIndexerSource(source);

function run(providerId) {
  const sandbox = {
    providerId,
    dirKeyOf: () => 'dir-from-file',
    history_1: { detectRuntimeShell: () => 'detected-shell' },
    require: (request) => request === './historyVisibility.cjs'
      ? {
          buildIndexedCodexSummary: (partial) => ({ ...partial, providerId: 'codex', __helperApplied: true }),
          buildIndexedCodexDetails: (partial) => partial,
        }
      : {},
  };
  vm.runInNewContext(patched, sandbox);
  return sandbox.rescanSnippet({
    id: 'session-id',
    title: 'title',
    date: 123,
    rawDate: '2026-04-06T00:00:00.000Z',
    dirKey: '',
    preview: 'sample preview',
    projectHash: 'project-hash',
    resumeMode: 'resume',
    resumeId: 'resume-id',
    runtimeShell: 'bash',
    subProvider: 'openai',
    source: 'vscode',
    originator: 'Codex Desktop',
    cwd: 'D:\\codex\\kaoyan-miniapp-mvp',
  }, 'D:\\codex\\kaoyan-miniapp-mvp\\.codex\\session.jsonl');
}
console.log('codex_result=' + JSON.stringify(run('codex')));
console.log('gemini_result=' + JSON.stringify(run('gemini')));
"@ | node -
```

## 3. 预期结果

- `resources\app.asar.bak-*` 已生成
- 首次重启后 CodexFlow 重新索引 Codex 历史
- 当前 workspace 仍为 `C:\Users\17795\Desktop` 时，历史列表不再空白
- 能看到带 `[cliproxyapi · ...]` / `[cpa_legacy · ...]` / `[openai · ...]` 前缀的旧会话
- 项目内命中存在时仍优先显示项目内历史
- installed generic summary 路径不会把非 codex provider 强制改写成 codex

## 4. 回滚命令

```powershell
Copy-Item -LiteralPath 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406044547' -Destination 'C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar' -Force
```

> 若需要回到第一次补丁前的原始安装版，可改用 `app.asar.bak-20260406042430`。

## 5. 实际执行记录

### 5.1 自动化验证结果

执行：

```powershell
node --test .\scripts\codexflow\tests\*.test.cjs
```

结果：`pass 18 / fail 0`

本轮新增/强化验证点：

- installed generic summary 路径在 `providerId === "codex"` 时仍会走 `buildIndexedCodexSummary(...)`
- installed generic summary 路径在 `providerId !== "codex"` 时保留原 summary 语义，不再被强制改成 codex
- installed variant 的真实锚点兼容仍然成立

### 5.2 review 指出问题的复现与修正

review 指出的阻塞问题已被复现：上一版 `patchInstalledFiles.cjs` 会把 installed generic summary 块统一替换成 `historyVisibility.buildIndexedCodexSummary(...)`，而该 helper 会强制写回 `providerId: 'codex'`，从而可能误伤非 codex provider。

本轮修正方式：

- **literal `providerId: "codex"` summary 块**：继续直接走 `buildIndexedCodexSummary(...)`
- **generic `providerId` summary 块**：改成
  - 先保留原始 `summaryBase`
  - 仅在 `providerId === "codex"` 时走 `buildIndexedCodexSummary({...summaryBase, subProvider/source/originator/cwd})`
  - 其他 provider 直接返回 `summaryBase`

因此，这次不是简单宣称“完全不改变语义”，而是：

- 纠正了上一版安装兼容修复过宽的问题
- 把 installed generic summary 路径收窄回 **仅 codex provider 才注入 codex helper** 的预期语义

### 5.3 纠正性重打补丁流程

由于 `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar` 之前已经带有过宽语义的 patched 版本，本轮按以下步骤纠正：

1. 停止所有 `CodexFlow.exe`
2. 使用 `app.asar.bak-20260406042430` 覆盖回 `resources\app.asar`
3. 校验恢复后 `app.asar` 与 `app.asar.bak-20260406042430` 哈希一致
4. 用修正后的 patcher 重新执行真实补丁
5. 生成新的纠正性备份：`app.asar.bak-20260406044547`
6. 自动重启 CodexFlow

成功输出：

```text
RESTORED_BASELINE_FROM=C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406042430
EXTRACT_ROOT=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app
BACKUP_CREATED=C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\resources\app.asar.bak-20260406044547
PATCHED_ASAR=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar
LAUNCH_STARTED=C:\Users\17795\AppData\Local\CodexFlow\launch-codexflow.cmd
```

### 5.4 纠正后安装产物校验

纠正性重打补丁后：

- 当前安装版 `app.asar` SHA-256：`1DF2B87B02AE1A0F3693F3DFEACD9E2EE8D296150F058E85092CBF67C3E6BEC8`
- `app.patched.asar` SHA-256：`1DF2B87B02AE1A0F3693F3DFEACD9E2EE8D296150F058E85092CBF67C3E6BEC8`
- 原始基线备份 `app.asar.bak-20260406042430` SHA-256：`42287497EFB8ACACBFC25A4EDE045EEAE82DDE8F4841C8DEFC8C70229DA1CAD2`
- 纠正性重打补丁生成的新备份 `app.asar.bak-20260406044547` SHA-256：`42287497EFB8ACACBFC25A4EDE045EEAE82DDE8F4841C8DEFC8C70229DA1CAD2`

结论：当前安装目录中的 `resources\app.asar` 已被“修正后”的 patched 版本替换；纠正性重打补丁前已先恢复到原始基线。

### 5.5 启动日志与进程观察

`C:\Users\17795\AppData\Local\CodexFlow\launch.log` 尾部包含本轮纠正性重启记录：

- `==== [2026/04/06 ... 4:45:48.77] launch request ====`

`Get-Process -Name 'CodexFlow'` 显示 4 个 `CodexFlow.exe` 进程于 `2026/04/06 04:45:50` 启动，路径均为：

- `C:\Users\17795\AppData\Local\CodexFlow\0.6.0\win-unpacked\CodexFlow.exe`

同时，`C:\Users\17795\.codexia\settings.json` 在纠正性重打补丁后仍保持：

- `workspace.cwd = \\?\C:\Users\17795\Desktop`
- `workspace.projects = ["\\\\?\\C:\\Users\\17795\\Desktop"]`

### 5.6 已落到安装产物的关键代码证据

来自 `C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app\dist\electron\main.js`：

- `const { selectHistorySessions } = require("./historyVisibility.cjs");`
- `const selection = selectHistorySessions({ filtered: sorted, all, offset, limit });`
- 返回项包含：`subProvider`、`cwd`、`fallbackReason`

来自 `C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app\dist\electron\indexer.js`：

- codex summary 路径会调用 `historyVisibility.buildIndexedCodexSummary(...)`
- codex details 路径会调用 `historyVisibility.buildIndexedCodexDetails(...)`
- generic `providerId` summary 路径已改成 `summaryBase + providerId === "codex"` 条件注入

## 6. 人工 UI 复核清单

1. 保持 selected workspace 为 `C:\Users\17795\Desktop` 不变。
2. 打开 CodexFlow 历史列表，确认不再空白。
3. 至少看到一条 `[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] ...`。
4. 至少看到一条 `[openai · ...] ...` 或 `[cliproxyapi · ...] ...`。
5. 切回 `D:\codex\kaoyan-miniapp-mvp` 对应项目后，项目内历史优先，不应总是落到 fallback。

## 7. 证据分层

### 7.1 可直接自动化验证的事实

1. **纠正性重打补丁前，安装版已先恢复到原始基线**
   - 直接证据：`RESTORED_BASELINE_FROM=...app.asar.bak-20260406042430`
   - 直接证据：恢复后 `app.asar` 与 `app.asar.bak-20260406042430` 哈希一致

2. **修正后的 patcher 已成功重打到真实安装目录**
   - 直接证据：`BACKUP_CREATED=...app.asar.bak-20260406044547`
   - 直接证据：`PATCHED_ASAR=C:\Users\17795\AppData\Local\Temp\codexflow-history-visibility\app.patched.asar`
   - 直接证据：当前安装版 `app.asar` 与 `app.patched.asar` 哈希一致

3. **CodexFlow 已被真实重启，且 selected workspace 未被改动**
   - 直接证据：`launch.log` 中 `2026/04/06 04:45:48.77` 的 launch request
   - 直接证据：4 个 `CodexFlow.exe` 进程于 `2026/04/06 04:45:50` 启动
   - 直接证据：`C:\Users\17795\.codexia\settings.json` 仍是 `\\?\C:\Users\17795\Desktop`

4. **真实旧会话元数据中确实存在需要展示的 provider/cwd 组合**
   - 直接证据：helper 回放统计得到：
     - `cliproxyapi`: `99`
     - `openai`: `54`
     - `cpa_legacy`: `20`
   - 直接证据：helper 回放可生成真实前缀样例：
     - `[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] sample preview`
     - `[openai · D:\codex] sample preview`
     - `[cliproxyapi · D:\codex\zc] sample preview`

5. **helper 级回放已验证 fallback / project 优先语义**
   - 直接证据：基于真实会话样本运行 `selectHistorySessions(...)` 得到：
     - `desktopFiltered = 0`
     - `desktopMode = "fallback"`
     - `desktopPreview0 = "[cpa_legacy · D:\codex\kaoyan-miniapp-mvp] sample preview"`
     - `projectFiltered = 54`
     - `projectMode = "project"`
     - `projectPreview0 = "[openai · D:\codex\kaoyan-miniapp-mvp] sample preview"`

6. **installed generic summary 路径已明确避免误伤非 codex provider**
   - 直接证据：`node --test .\scripts\codexflow\tests\*.test.cjs` 中新增回归测试通过
   - 直接证据：运行 `2.8` 的 VM 回放命令得到：
     - `codex_result.providerId = "codex"` 且 `__helperApplied = true`
     - `gemini_result.providerId = "gemini"`，且不含 `__helperApplied`、`cwd`、`subProvider`
   - 说明：non-codex provider 在 generic summary 路径下保留原 summary 语义，不再被 helper 强制改成 codex

### 7.2 仍需人工点击 UI 复核的项

1. **“当前 workspace 为 Desktop 时，历史列表不再空白”**
   - 当前没有直接 Electron UI 自动化能力；未直接点击列表确认。

2. **“能在 CodexFlow 历史面板里看到 `[cpa_legacy · ...]` / `[openai · ...]` / `[cliproxyapi · ...]` 条目”**
   - 已通过 helper + 真实会话元数据证明前缀可生成、原始数据存在，但未直接拍到 GUI 列表。

3. **“首次重启后 CodexFlow 重新索引 Codex 历史”**
   - 本次未拿到 GUI 内部索引进度条或列表刷新截图。
   - `C:\Users\17795\.codexia\data.db` 的 `sessions` 表并不能作为本项的充分证据，因此本项仍待人工 UI 复核。

4. **“切回 `D:\codex\kaoyan-miniapp-mvp` 后项目内历史优先，不总是落到 fallback”**
   - helper 级回放已证明真实样本下 `projectMode = "project"`，但最终 GUI 呈现仍需人工切换项目再确认一次。

## 8. 本轮修复涉及文件

- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\lib\patchInstalledFiles.cjs`
- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\codexflow-patch.test.cjs`
- `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\docs\codexflow_history_visibility_verification_2026-04-06.md`
- 复用已有 fixture：
  - `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\fixtures\electron\indexer.installed.before.js`
  - `D:\codex\kaoyan-miniapp-mvp\.worktrees\codexflow-history-visibility\scripts\codexflow\tests\fixtures\electron\main.installed.before.js`
