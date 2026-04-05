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

const normalizeDate = (value) => {
  if (!value) {
    return 0;
  }
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
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
    providerId: 'codex',
    subProvider: partial?.subProvider,
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
  const safeOffset = Number.isFinite(offset) ? offset : 0;
  const hasLimit = Number.isFinite(limit);

  if (Array.isArray(filtered) && filtered.length > 0) {
    const end = hasLimit ? safeOffset + limit : undefined;
    return {
      mode: 'project',
      sessions: filtered.slice(safeOffset, end),
    };
  }

  const codexOnly = Array.isArray(all)
    ? all.filter((session) => session?.providerId === 'codex')
    : [];
  const sorted = codexOnly
    .slice()
    .sort((a, b) => normalizeDate(b?.date) - normalizeDate(a?.date));
  const annotated = sorted.map((session) => ({
    ...session,
    fallbackReason: 'project_miss',
  }));
  const end = hasLimit ? safeOffset + limit : undefined;

  return {
    mode: 'fallback',
    sessions: annotated.slice(safeOffset, end),
  };
};

module.exports = {
  loadJsonl,
  mergeCodexMetadata,
  buildIndexedCodexSummary,
  buildIndexedCodexDetails,
  selectHistorySessions,
};
