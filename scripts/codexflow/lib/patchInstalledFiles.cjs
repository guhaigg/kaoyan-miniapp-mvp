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

const replaceOnceRegex = (source, pattern, replacer, label) => {
  const matches = [...source.matchAll(pattern)];
  if (matches.length === 0) {
    throw new Error(`Missing patch anchor: ${label}`);
  }
  if (matches.length > 1) {
    throw new Error(`Multiple patch anchors found for: ${label}`);
  }
  const match = matches[0];
  return source.replace(pattern, (...args) => replacer(...args.slice(0, -2)));
};

const replaceAllRegex = (source, pattern, replacer, label) => {
  const matches = [...source.matchAll(pattern)];
  if (matches.length === 0) {
    throw new Error(`Missing patch anchor: ${label}`);
  }
  return source.replace(pattern, (...args) => replacer(...args.slice(0, -2)));
};

const replaceAllRegexOptional = (source, pattern, replacer) => {
  const matches = [...source.matchAll(pattern)];
  if (matches.length === 0) {
    return source;
  }
  return source.replace(pattern, (...args) => replacer(...args.slice(0, -2)));
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

  text = replaceOnceRegex(
    text,
    /(            rs\.on\('end', \(\) => \{\n)([\s\S]*?)(                resolve\(\{ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell \}\);\n            \}\);)/g,
    (full, start, body) =>
      `${start}${body}                resolve(historyVisibility.buildIndexedCodexDetails({ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n            });`,
    'indexer.details.resolve.end'
  );

  text = replaceOnceRegex(
    text,
    /(            rs\.on\('error', \(\) => \{\n)([\s\S]*?)(                resolve\(\{ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell \}\);\n            \}\);)/g,
    (full, start, body) =>
      `${start}${body}                resolve(historyVisibility.buildIndexedCodexDetails({ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n            });`,
    'indexer.details.resolve.error'
  );

  text = replaceOnce(
    text,
    "        catch {\n            if (runtimeShell === 'unknown')\n                runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n            const finalResumeId = resumeId || id;\n            resolve({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, resumeMode, resumeId: finalResumeId, runtimeShell });\n        }",
    "        catch {\n            if (runtimeShell === 'unknown')\n                runtimeShell = (0, history_1.detectRuntimeShell)(fp);\n            const finalResumeId = resumeId || id;\n            resolve(historyVisibility.buildIndexedCodexDetails({ providerId: \"codex\", id, title, date, filePath: fp, messages, skippedLines: skipped, resumeMode, resumeId: finalResumeId, runtimeShell, subProvider: modelProvider, source: sourceHint, originator }));\n        }",
    'indexer.details.resolve.catch'
  );

  text = replaceAllRegexOptional(
    text,
    /(^[ ]*)const summary = \{\n\1    providerId: "codex",\n\1    id: details\.id,\n\1    title: details\.title,\n\1    date: details\.date,\n\1    filePath: fp,\n\1    rawDate: details\.rawDate,\n\1    dirKey: details\.dirKey \|\| dirKeyOf\(fp\),\n\1    preview: details\.preview,\n\1    projectHash: details\.projectHash,\n\1    resumeMode: details\.resumeMode,\n\1    resumeId: details\.resumeId,\n\1    runtimeShell: details\.runtimeShell && details\.runtimeShell !== 'unknown' \? details\.runtimeShell : \(0, history_1\.detectRuntimeShell\)\(fp\),\n\1\};/gm,
    (full, indent) =>
      `${indent}const summary = historyVisibility.buildIndexedCodexSummary({\n${indent}    providerId: "codex",\n${indent}    id: details.id,\n${indent}    title: details.title,\n${indent}    date: details.date,\n${indent}    filePath: fp,\n${indent}    rawDate: details.rawDate,\n${indent}    dirKey: details.dirKey || dirKeyOf(fp),\n${indent}    preview: details.preview,\n${indent}    projectHash: details.projectHash,\n${indent}    resumeMode: details.resumeMode,\n${indent}    resumeId: details.resumeId,\n${indent}    runtimeShell: details.runtimeShell && details.runtimeShell !== 'unknown' ? details.runtimeShell : (0, history_1.detectRuntimeShell)(fp),\n${indent}    subProvider: details.subProvider,\n${indent}    source: details.source,\n${indent}    originator: details.originator,\n${indent}    cwd: details.cwd,\n${indent}});`,
  );

  text = replaceAllRegexOptional(
    text,
    /(^[ ]*)const summary = \{\n\1    providerId,\n\1    id: details\.id,\n\1    title: details\.title,\n\1    date: details\.date,\n\1    filePath: fp,\n\1    rawDate: details\.rawDate,\n\1    dirKey: details\.dirKey \|\| dirKeyOf\(fp\),\n\1    preview: details\.preview,\n\1    projectHash: details\.projectHash,\n\1    resumeMode: details\.resumeMode,\n\1    resumeId: details\.resumeId,\n\1    runtimeShell: details\.runtimeShell && details\.runtimeShell !== 'unknown' \? details\.runtimeShell : \(0, history_1\.detectRuntimeShell\)\(fp\),\n\1\};/gm,
    (full, indent) =>
      `${indent}const summaryBase = {\n${indent}    providerId,\n${indent}    id: details.id,\n${indent}    title: details.title,\n${indent}    date: details.date,\n${indent}    filePath: fp,\n${indent}    rawDate: details.rawDate,\n${indent}    dirKey: details.dirKey || dirKeyOf(fp),\n${indent}    preview: details.preview,\n${indent}    projectHash: details.projectHash,\n${indent}    resumeMode: details.resumeMode,\n${indent}    resumeId: details.resumeId,\n${indent}    runtimeShell: details.runtimeShell && details.runtimeShell !== 'unknown' ? details.runtimeShell : (0, history_1.detectRuntimeShell)(fp),\n${indent}};\n${indent}const summary = providerId === "codex"\n${indent}    ? historyVisibility.buildIndexedCodexSummary({\n${indent}        ...summaryBase,\n${indent}        subProvider: details.subProvider,\n${indent}        source: details.source,\n${indent}        originator: details.originator,\n${indent}        cwd: details.cwd,\n${indent}    })\n${indent}    : summaryBase;`,
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

  text = replaceOnceRegex(
    text,
    /(^[ ]*)const sorted = filtered\.sort\(\(a, b\) => b\.date - a\.date\);\n\1const offset = Math\.max\(0, Number\(args\.offset \|\| 0\)\);\n\1const end = args\.limit \? offset \+ Number\(args\.limit\) : undefined;\n\1const sliced = sorted\.slice\(offset, end\);\n\1const mapped = sliced\.map\(\(x\) => \(\{\n\1    providerId: x\.providerId \|\| "codex",\n\1    id: x\.id,\n\1    title: x\.title,\n\1    date: x\.date,\n\1    filePath: x\.filePath,\n\1    rawDate: x\.rawDate,\n\1    preview: x\.preview,\n\1    projectHash: x\.projectHash,\n\1    resumeMode: x\.resumeMode,\n\1    resumeId: x\.resumeId,\n\1    runtimeShell: x\.runtimeShell,\n\1\}\)\);\n\1return \{ ok: true, sessions: mapped \};/gm,
    (full, indent) =>
      `${indent}const sorted = filtered.sort((a, b) => b.date - a.date);\n${indent}const offset = Math.max(0, Number(args.offset || 0));\n${indent}const limit = args.limit ? Number(args.limit) : undefined;\n${indent}const selection = selectHistorySessions({ filtered: sorted, all, offset, limit });\n${indent}const mapped = selection.sessions.map((x) => ({\n${indent}    providerId: x.providerId || "codex",\n${indent}    id: x.id,\n${indent}    title: x.title,\n${indent}    date: x.date,\n${indent}    filePath: x.filePath,\n${indent}    rawDate: x.rawDate,\n${indent}    preview: x.preview,\n${indent}    projectHash: x.projectHash,\n${indent}    resumeMode: x.resumeMode,\n${indent}    resumeId: x.resumeId,\n${indent}    runtimeShell: x.runtimeShell,\n${indent}    subProvider: x.subProvider,\n${indent}    cwd: x.cwd,\n${indent}    fallbackReason: x.fallbackReason,\n${indent}}));\n${indent}return { ok: true, sessions: mapped };`,
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
