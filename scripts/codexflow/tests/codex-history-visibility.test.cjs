const path = require('node:path');
const { test } = require('node:test');
const assert = require('node:assert/strict');

const {
  loadJsonl,
  mergeCodexMetadata,
  buildIndexedCodexSummary,
  buildIndexedCodexDetails,
  selectHistorySessions,
} = require('../lib/historyVisibility.cjs');

const fixturesDir = path.join(__dirname, 'fixtures', 'codex');

const loadFixture = (name) => loadJsonl(path.join(fixturesDir, name));

test('mergeCodexMetadata keeps model_provider and cwd', () => {
  const sessionMeta = loadFixture('session-meta.jsonl')[0];
  const sessionIndex = loadFixture('session-index.jsonl')[0];
  const history = loadFixture('history.jsonl')[0];
  const sessionFilePath = path.join(fixturesDir, 'history.jsonl');

  const result = mergeCodexMetadata({
    sessionFilePath,
    sessionMeta,
    sessionIndex,
    history,
  });

  assert.equal(result.model_provider, sessionMeta.payload.model_provider);
  assert.equal(result.cwd, sessionMeta.payload.cwd);
  assert.equal(result.title, sessionIndex.thread_name);
  assert.equal(result.preview, history.text);
  assert.equal(result.originator, sessionMeta.payload.originator);
  assert.equal(result.source, sessionMeta.payload.source);
});

test('buildIndexedCodexSummary prefixes preview with provider and cwd', () => {
  const summary = buildIndexedCodexSummary({
    preview: '你好',
    subProvider: 'cpa_legacy',
    cwd: 'D:\\codex\\kaoyan-miniapp-mvp',
  });

  assert.equal(
    summary.preview,
    '[cpa_legacy · D:\\codex\\kaoyan-miniapp-mvp] 你好'
  );
  assert.equal(summary.providerId, 'codex');
  assert.equal(summary.subProvider, 'cpa_legacy');
});

test('buildIndexedCodexDetails keeps metadata fields', () => {
  const details = buildIndexedCodexDetails({
    subProvider: 'cpa_legacy',
    source: 'vscode',
    originator: 'Codex Desktop',
    messages: [{ role: 'user', content: 'hi' }],
    skippedLines: 2,
  });

  assert.equal(details.subProvider, 'cpa_legacy');
  assert.equal(details.source, 'vscode');
  assert.equal(details.originator, 'Codex Desktop');
  assert.deepEqual(details.messages, [{ role: 'user', content: 'hi' }]);
  assert.equal(details.skippedLines, 2);
});

test('selectHistorySessions falls back to all when filtered empty', () => {
  const result = selectHistorySessions({
    filtered: [],
    all: [
      {
        id: 'a',
        providerId: 'codex',
        date: '2026-04-05T10:00:00Z',
      },
      {
        id: 'b',
        providerId: 'other',
        date: '2026-04-06T10:00:00Z',
      },
      {
        id: 'c',
        providerId: 'codex',
        date: '2026-04-06T09:00:00Z',
      },
      {
        id: 'd',
        providerId: 'codex',
        date: '2026-04-04T09:00:00Z',
      },
    ],
    offset: 1,
    limit: 1,
  });

  assert.equal(result.mode, 'fallback');
  assert.equal(result.sessions.length, 1);
  assert.deepEqual(
    result.sessions.map((session) => session.providerId),
    ['codex']
  );
  assert.equal(result.sessions[0].id, 'a');
  assert.equal(result.sessions[0].fallbackReason, 'project_miss');
});
