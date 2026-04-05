const path = require('node:path');
const fs = require('node:fs');
const os = require('node:os');
const vm = require('node:vm');
const { test } = require('node:test');
const assert = require('node:assert/strict');

const {
  patchIndexerSource,
  patchMainSource,
  applyPatchToExtractedApp,
} = require('../lib/patchInstalledFiles.cjs');

const fixturesDir = path.join(__dirname, 'fixtures', 'electron');

const readFixture = (name) =>
  fs.readFileSync(path.join(fixturesDir, name), 'utf8');

const runInstalledRescanSnippet = ({ providerId }) => {
  const source = readFixture('indexer.installed.before.js');
  const patched = patchIndexerSource(source);
  const sandbox = {
    providerId,
    dirKeyOf: () => 'dir-from-file',
    history_1: { detectRuntimeShell: () => 'detected-shell' },
    require: (request) => {
      if (request === './historyVisibility.cjs') {
        return {
          buildIndexedCodexSummary: (partial) => ({
            ...partial,
            providerId: 'codex',
            preview: `[patched] ${partial.preview || ''}`.trim(),
            __helperApplied: true,
          }),
          buildIndexedCodexDetails: (partial) => partial,
        };
      }
      return {};
    },
  };

  vm.runInNewContext(patched, sandbox);
  const result = sandbox.rescanSnippet(
    {
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
    },
    'D:\\codex\\kaoyan-miniapp-mvp\\.codex\\session.jsonl'
  );

  return { patched, result };
};

test('patchIndexerSource injects history visibility helpers', () => {
  const source = readFixture('indexer.before.js');
  const patched = patchIndexerSource(source);

  assert.match(
    patched,
    /const historyVisibility = require\("\.\/historyVisibility\.cjs"\);/
  );
  assert.match(patched, /const VERSION = "v10";/);
  assert.match(patched, /subProvider/);
  assert.match(patched, /buildIndexedCodexSummary/);
  assert.match(patched, /buildIndexedCodexDetails/);
});

test('patchIndexerSource supports installed indexer variant with dirKey assignment before resolve', () => {
  const source = readFixture('indexer.installed.before.js');
  const patched = patchIndexerSource(source);

  assert.match(patched, /buildIndexedCodexDetails/);
  assert.match(patched, /buildIndexedCodexSummary/);
  assert.match(
    patched,
    /resolve\(historyVisibility\.buildIndexedCodexDetails\(\{ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator \}\)\);/
  );
  assert.match(
    patched,
    /const summary = providerId === "codex"[\s\S]*buildIndexedCodexSummary[\s\S]*: summaryBase;/
  );
});

test('patchIndexerSource applies installed generic summary helper only for codex provider', () => {
  const { result } = runInstalledRescanSnippet({ providerId: 'codex' });

  assert.equal(result.providerId, 'codex');
  assert.equal(result.__helperApplied, true);
  assert.match(result.preview, /^\[patched\] sample preview$/);
  assert.equal(result.cwd, 'D:\\codex\\kaoyan-miniapp-mvp');
  assert.equal(result.subProvider, 'openai');
});

test('patchIndexerSource keeps installed generic summary semantics for non-codex provider', () => {
  const { result } = runInstalledRescanSnippet({ providerId: 'gemini' });

  assert.equal(result.providerId, 'gemini');
  assert.equal(result.__helperApplied, undefined);
  assert.equal(result.preview, 'sample preview');
  assert.equal(result.cwd, undefined);
  assert.equal(result.subProvider, undefined);
});

test('patchMainSource injects history selection metadata', () => {
  const source = readFixture('main.before.js');
  const patched = patchMainSource(source);

  assert.match(patched, /selectHistorySessions/);
  assert.match(patched, /fallbackReason/);
  assert.match(patched, /subProvider/);
  assert.match(patched, /cwd/);
});

test('patchMainSource supports installed main variant with deeper indentation', () => {
  const source = readFixture('main.installed.before.js');
  const patched = patchMainSource(source);

  assert.match(patched, /selectHistorySessions/);
  assert.match(patched, /fallbackReason/);
  assert.match(patched, /selection\.sessions\.map/);
});

test('patchMainSource preserves sorted semantics', () => {
  const source = readFixture('main.before.js');
  const patched = patchMainSource(source);

  assert.match(
    patched,
    /const sorted = filtered\.sort\(\(a, b\) => b\.date - a\.date\);/
  );
  assert.match(
    patched,
    /selectHistorySessions\(\{ filtered: sorted, all, offset, limit \}\)/
  );
});

test('applyPatchToExtractedApp patches files and copies helper', () => {
  const tmpRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'codexflow-patch-'));
  const distDir = path.join(tmpRoot, 'dist', 'electron');
  fs.mkdirSync(distDir, { recursive: true });

  const indexerPath = path.join(distDir, 'indexer.js');
  const mainPath = path.join(distDir, 'main.js');
  fs.writeFileSync(indexerPath, readFixture('indexer.before.js'), 'utf8');
  fs.writeFileSync(mainPath, readFixture('main.before.js'), 'utf8');

  const helperSource = path.join(tmpRoot, 'helper.cjs');
  fs.writeFileSync(helperSource, 'module.exports = { ok: true };', 'utf8');

  applyPatchToExtractedApp({ extractRoot: tmpRoot, helperSource });

  const helperTarget = path.join(distDir, 'historyVisibility.cjs');
  assert.equal(fs.existsSync(helperTarget), true);
  assert.equal(
    fs.readFileSync(helperTarget, 'utf8').includes('module.exports'),
    true
  );

  const patchedIndexer = fs.readFileSync(indexerPath, 'utf8');
  const patchedMain = fs.readFileSync(mainPath, 'utf8');
  assert.match(patchedIndexer, /historyVisibility/);
  assert.match(patchedMain, /selectHistorySessions/);
});

test('patchMainSource throws when anchors are missing', () => {
  assert.throws(
    () => patchMainSource('x'),
    /Missing patch anchor/
  );
});
