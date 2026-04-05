const fs = require('node:fs');
const path = require('node:path');

const detectNewline = (source) => (source.includes('\r\n') ? '\r\n' : '\n');
const normalizeNewlines = (source) => source.replace(/\r\n/g, '\n');

const replaceOnce = (source, search, replacement, label) => {
  const idx = source.indexOf(search);
  if (idx === -1) {
    throw new Error(`Missing patch anchor: ${label}`);
  }
  const next = source.indexOf(search, idx + search.length);
  if (next !== -1) {
    throw new Error(`Multiple patch anchors found for: ${label}`);
  }
  return `${source.slice(0, idx)}${replacement}${source.slice(idx + search.length)}`;
};

const patchIndexerSource = (source) => {
  const newline = detectNewline(source);
  let text = normalizeNewlines(source);

  text = replaceOnce(
    text,
    'const preview_1 = require("./agentSessions/shared/preview");',
    'const preview_1 = require("./agentSessions/shared/preview");\nconst historyVisibility = require("./historyVisibility.cjs");',
    'indexer.historyVisibility.require'
  );

  text = replaceOnce(
    text,
    'const VERSION = "v9";',
    'const VERSION = "v10";',
    'indexer.VERSION'
  );

  text = replaceOnce(
    text,
    '    let rawDate = undefined;\n    let dbgSrc = "";',
    '    let rawDate = undefined;\n    let modelProvider = "";\n    let sourceHint = "";\n    let originator = "";\n    let dbgSrc = "";',
    'indexer.summary.vars'
  );

  text = replaceOnce(
    text,
    "            if (typeof obj.payload?.cwd === 'string') {\n                cwd = obj.payload.cwd;\n                dbgSrc = 'json.payload.cwd';\n            }",
    "            if (typeof obj.payload?.cwd === 'string') {\n                cwd = obj.payload.cwd;\n                dbgSrc = 'json.payload.cwd';\n            }\n            if (typeof obj.payload?.model_provider === 'string') {\n                modelProvider = obj.payload.model_provider;\n            }\n            if (typeof obj.payload?.source === 'string') {\n                sourceHint = obj.payload.source;\n            }\n            if (typeof obj.payload?.originator === 'string') {\n                originator = obj.payload.originator;\n            }",
    'indexer.summary.session_meta'
  );

  text = replaceOnce(
    text,
    '    let rawDate = undefined;\n    let cwd = "";\n    let dirKey = "";',
    '    let rawDate = undefined;\n    let modelProvider = "";\n    let sourceHint = "";\n    let originator = "";\n    let cwd = "";\n    let dirKey = "";',
    'indexer.details.vars'
  );

  text = replaceOnce(
    text,
    '                                    const payload = obj.payload || {};',
    '                                    const payload = obj.payload || {};\n                                    if (typeof payload.model_provider === "string")\n                                        modelProvider = payload.model_provider;\n                                    if (typeof payload.source === "string")\n                                        sourceHint = payload.source;\n                                    if (typeof payload.originator === "string")\n                                        originator = payload.originator;',
    'indexer.details.session_meta'
  );

  text = replaceOnce(
    text,
    '    return { providerId: "codex", id, title, date, filePath: fp, rawDate, dirKey, resumeMode, resumeId, runtimeShell };',
    '    return historyVisibility.buildIndexedCodexSummary({ providerId: "codex", id, title, date, filePath: fp, rawDate, dirKey, resumeMode, resumeId, runtimeShell, cwd, subProvider: modelProvider, source: sourceHint, originator });',
    'indexer.summary.return'
  );

  text = replaceOnce(
    text,
    "            rs.on('end', () => {\n                if (runtimeShell === 'unknown')\n                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n                const finalResumeId = resumeId || id;\n                resolve({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell });\n            });",
    "            rs.on('end', () => {\n                if (runtimeShell === 'unknown')\n                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n                const finalResumeId = resumeId || id;\n                resolve(historyVisibility.buildIndexedCodexDetails({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n            });",
    'indexer.details.resolve.end'
  );

  text = replaceOnce(
    text,
    "            rs.on('error', () => {\n                if (runtimeShell === 'unknown')\n                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n                const finalResumeId = resumeId || id;\n                resolve({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell });\n            });",
    "            rs.on('error', () => {\n                if (runtimeShell === 'unknown')\n                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n                const finalResumeId = resumeId || id;\n                resolve(historyVisibility.buildIndexedCodexDetails({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n            });",
    'indexer.details.resolve.error'
  );

  text = replaceOnce(
    text,
    "        catch {\n            if (runtimeShell === 'unknown')\n                runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n            const finalResumeId = resumeId || id;\n            resolve({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, resumeMode, resumeId: finalResumeId, runtimeShell });\n        }",
    "        catch {\n            if (runtimeShell === 'unknown')\n                runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n            const finalResumeId = resumeId || id;\n            resolve(historyVisibility.buildIndexedCodexDetails({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n        }",
    'indexer.details.resolve.catch'
  );

  text = replaceOnce(
    text,
    "    const summary = {\n        providerId: \"codex\",\n        id: details.id,\n        title: details.title,\n        date: details.date,\n        filePath: fp,\n        rawDate: details.rawDate,\n        dirKey: details.dirKey || dirKeyOf(fp),\n        preview: details.preview,\n        projectHash: details.projectHash,\n        resumeMode: details.resumeMode,\n        resumeId: details.resumeId,\n        runtimeShell: details.runtimeShell && details.runtimeShell !== 'unknown' ? details.runtimeShell : (0, history_1.detectRuntimeShell)(fp),\n    };",
    "    const summary = historyVisibility.buildIndexedCodexSummary({\n        providerId: \"codex\",\n        id: details.id,\n        title: details.title,\n        date: details.date,\n        filePath: fp,\n        rawDate: details.rawDate,\n        dirKey: details.dirKey || dirKeyOf(fp),\n        preview: details.preview,\n        projectHash: details.projectHash,\n        resumeMode: details.resumeMode,\n        resumeId: details.resumeId,\n        runtimeShell: details.runtimeShell && details.runtimeShell !== 'unknown' ? details.runtimeShell : (0, history_1.detectRuntimeShell)(fp),\n        subProvider: details.subProvider,\n        source: details.source,\n        originator: details.originator,\n        cwd: details.cwd,\n    });",
    'indexer.rescan.summary'
  );

  if (newline === '\r\n') {
    return text.replace(/\n/g, '\r\n');
  }
  return text;
};

const patchMainSource = (source) => {
  const newline = detectNewline(source);
  let text = normalizeNewlines(source);

  text = replaceOnce(
    text,
    'const indexer_1 = require("./indexer");',
    'const indexer_1 = require("./indexer");\nconst { selectHistorySessions } = require("./historyVisibility.cjs");',
    'main.historyVisibility.require'
  );

  text = replaceOnce(
    text,
    "        const sorted = filtered.sort((a, b) => b.date - a.date);\n        const offset = Math.max(0, Number(args.offset || 0));\n        const end = args.limit ? offset + Number(args.limit) : undefined;\n        const sliced = sorted.slice(offset, end);\n        const mapped = sliced.map((x) => ({\n            providerId: x.providerId || \"codex\",\n            id: x.id,\n            title: x.title,\n            date: x.date,\n            filePath: x.filePath,\n            rawDate: x.rawDate,\n            preview: x.preview,\n            projectHash: x.projectHash,\n            resumeMode: x.resumeMode,\n            resumeId: x.resumeId,\n            runtimeShell: x.runtimeShell,\n        }));\n        return { ok: true, sessions: mapped };",
    "        const sorted = filtered.sort((a, b) => b.date - a.date);\n        const offset = Math.max(0, Number(args.offset || 0));\n        const limit = args.limit ? Number(args.limit) : undefined;\n        const selection = selectHistorySessions({ filtered: sorted, all, offset, limit });\n        const mapped = selection.sessions.map((x) => ({\n            providerId: x.providerId || \"codex\",\n            id: x.id,\n            title: x.title,\n            date: x.date,\n            filePath: x.filePath,\n            rawDate: x.rawDate,\n            preview: x.preview,\n            projectHash: x.projectHash,\n            resumeMode: x.resumeMode,\n            resumeId: x.resumeId,\n            runtimeShell: x.runtimeShell,\n            subProvider: x.subProvider,\n            cwd: x.cwd,\n            fallbackReason: x.fallbackReason,\n        }));\n        return { ok: true, sessions: mapped };",
    'main.history.list'
  );

  if (newline === '\r\n') {
    return text.replace(/\n/g, '\r\n');
  }
  return text;
};

const writePatchedFile = (filePath, transform) => {
  const source = fs.readFileSync(filePath, 'utf8');
  const patched = transform(source);
  fs.writeFileSync(filePath, patched, 'utf8');
};

const applyPatchToExtractedApp = ({ extractRoot, helperSource }) => {
  if (!extractRoot) {
    throw new Error('extractRoot is required');
  }
  if (!helperSource) {
    throw new Error('helperSource is required');
  }
  const distDir = path.join(extractRoot, 'dist', 'electron');
  const helperTarget = path.join(distDir, 'historyVisibility.cjs');
  fs.copyFileSync(helperSource, helperTarget);
  writePatchedFile(path.join(distDir, 'indexer.js'), patchIndexerSource);
  writePatchedFile(path.join(distDir, 'main.js'), patchMainSource);
};

const parseArgs = (argv) => {
  const args = { extractRoot: undefined, helperSource: undefined };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--extract-root') {
      args.extractRoot = argv[i + 1];
      i += 1;
      continue;
    }
    if (arg === '--helper-source') {
      args.helperSource = argv[i + 1];
      i += 1;
      continue;
    }
  }
  return args;
};

if (require.main === module) {
  const { extractRoot, helperSource } = parseArgs(process.argv.slice(2));
  if (!extractRoot || !helperSource) {
    console.error('Usage: node patchInstalledFiles.cjs --extract-root <dir> --helper-source <file>');
    process.exit(1);
  }
  applyPatchToExtractedApp({ extractRoot, helperSource });
}

module.exports = {
  patchIndexerSource,
  patchMainSource,
  applyPatchToExtractedApp,
  replaceOnce,
};
