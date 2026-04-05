const fs = require('node:fs');

const loadJsonl = (filePath) => {
  const content = fs.readFileSync(filePath, 'utf8');
  return content
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => JSON.parse(line));
};

const coercePreview = (preview) => {
  if (typeof preview === 'string') {
    return preview.trim();
  }
  if (preview == null) {
    return '';
  }
  return String(preview).trim();
};

const buildPreviewPrefix = ({ subProvider, cwd }) => {
  const parts = [];
  if (subProvider) {
    parts.push(subProvider);
  }
  if (cwd) {
    parts.push(cwd);
  }
  if (parts.length === 0) {
    return '';
  }
  return `[${parts.join(' · ')}]`;
};

const mergeCodexMetadata = ({ sessionFilePath, sessionMeta, sessionIndex, history }) => {
  const payload = sessionMeta?.payload ?? {};
  return {
    sessionFilePath,
    id: payload.id ?? sessionIndex?.id ?? history?.session_id,
    title: sessionIndex?.thread_name,
    preview: history?.text,
    cwd: payload.cwd,
    originator: payload.originator,
    source: payload.source,
    model_provider: payload.model_provider,
    subProvider: payload.model_provider,
  };
};

const buildIndexedCodexSummary = (partial) => {
  const prefix = buildPreviewPrefix(partial);
  const preview = coercePreview(partial?.preview);
  const combined = prefix ? (preview ? `${prefix} ${preview}` : prefix) : preview;
  return {
    ...partial,
    preview: combined,
  };
};

const buildIndexedCodexDetails = (partial) => ({
  ...partial,
  subProvider: partial?.subProvider,
  source: partial?.source,
  originator: partial?.originator,
  messages: partial?.messages,
  skippedLines: partial?.skippedLines,
});

const selectHistorySessions = ({ filtered, all, offset, limit }) => {
  const preferred = Array.isArray(filtered) && filtered.length > 0 ? filtered : all;
  const safeOffset = Number.isFinite(offset) ? offset : 0;
  const safeLimit = Number.isFinite(limit) ? limit : preferred?.length ?? 0;
  if (!Array.isArray(preferred)) {
    return [];
  }
  return preferred.slice(safeOffset, safeOffset + safeLimit);
};

module.exports = {
  loadJsonl,
  mergeCodexMetadata,
  buildIndexedCodexSummary,
  buildIndexedCodexDetails,
  selectHistorySessions,
};
