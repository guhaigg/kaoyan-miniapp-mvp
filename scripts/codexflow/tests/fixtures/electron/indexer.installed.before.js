"use strict";
const preview_1 = require("./agentSessions/shared/preview");
const VERSION = "v9";
function parseSummary(fp, stat) {
    const first = "{}";
    let id = "";
    let title = "";
    let cwd = "";
    let rawDate = undefined;
    let dbgSrc = "";
    let resumeMode = 'unknown';
    let resumeId = undefined;
    let runtimeShell = 'unknown';
    try {
        const obj = JSON.parse(first);
        if (obj && obj.type === 'session_meta' && obj.payload) {
            if (obj.payload?.id)
                id = String(obj.payload.id);
            if (typeof obj.payload?.cwd === 'string') {
                cwd = obj.payload.cwd;
                dbgSrc = 'json.payload.cwd';
            }
            if (Object.prototype.hasOwnProperty.call(obj, 'timestamp')) {
                try {
                    rawDate = String(obj.timestamp);
                }
                catch {
                    rawDate = undefined;
                }
            }
            else if (Object.prototype.hasOwnProperty.call(obj.payload, 'timestamp')) {
                try {
                    rawDate = String(obj.payload.timestamp);
                }
                catch {
                    rawDate = undefined;
                }
            }
        }
    }
    catch { }
    if (runtimeShell === 'unknown')
        runtimeShell = 'bash';
    return { providerId: "codex", id, title, date, filePath: fp, rawDate, dirKey, resumeMode, resumeId, runtimeShell };
}
async function parseCodexDetails(fp, stat, opts) {
    const summaryOnly = !!opts?.summaryOnly;
    let id = "";
    let title = "";
    const date = stat.mtimeMs || 0;
    const messages = [];
    let skipped = 0;
    let rawDate = undefined;
    let cwd = "";
    let dirKey = "";
    let preview = undefined;
    let resumeMode = 'unknown';
    let resumeId = undefined;
    let runtimeShell = 'unknown';
    let prefixAcc = "";
    return await new Promise((resolve) => {
        try {
            const rs = node_fs_1.default.createReadStream(fp, { encoding: "utf8" });
            const flushLines = (text) => {
                const lines = text.split(/\r?\n/);
                for (const line of lines) {
                    if (!line)
                        continue;
                    try {
                        const obj = JSON.parse(line);
                        if (lineIndex === 0) {
                            try {
                                if (obj.type === 'session_meta' && obj.payload) {
                                    const payload = obj.payload || {};
                                    if (payload.id)
                                        id = String(payload.id);
                                    if (Object.prototype.hasOwnProperty.call(obj, 'timestamp')) {
                                        try {
                                            rawDate = String(obj.timestamp);
                                        }
                                        catch {
                                            rawDate = undefined;
                                        }
                                    }
                                    else if (Object.prototype.hasOwnProperty.call(payload, 'timestamp')) {
                                        try {
                                            rawDate = String(payload.timestamp);
                                        }
                                        catch {
                                            rawDate = undefined;
                                        }
                                    }
                                    try {
                                        const cand = String(payload.cwd || '');
                                        if (cand)
                                            cwd = cand;
                                    }
                                    catch { }
                                }
                            }
                            catch { }
                        }
                    }
                    catch { }
                }
            };
            rs.on('end', () => {
                if (cwd)
                    dirKey = dirKeyFromCwd(cwd);
                else
                    dirKey = dirKeyOf(fp);
                if (runtimeShell === 'unknown')
                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);
                const finalResumeId = resumeId || id;
                resolve({ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell });
            });
            rs.on('error', () => {
                if (cwd)
                    dirKey = dirKeyFromCwd(cwd);
                else
                    dirKey = dirKeyOf(fp);
                if (runtimeShell === 'unknown')
                    runtimeShell = (0, history_1.detectRuntimeShell)(fp);
                const finalResumeId = resumeId || id;
                resolve({ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, rawDate, cwd, dirKey, preview, resumeMode, resumeId: finalResumeId, runtimeShell });
            });
        }
        catch {
            if (runtimeShell === 'unknown')
                runtimeShell = (0, history_1.detectRuntimeShell)(fp);
            const finalResumeId = resumeId || id;
            resolve({ providerId: "codex", id, title, date, filePath: fp, messages, skippedLines: skipped, resumeMode, resumeId: finalResumeId, runtimeShell });
        }
    });
}
function rescanSnippet(details, fp) {
    const summary = {
        providerId,
        id: details.id,
        title: details.title,
        date: details.date,
        filePath: fp,
        rawDate: details.rawDate,
        dirKey: details.dirKey || dirKeyOf(fp),
        preview: details.preview,
        projectHash: details.projectHash,
        resumeMode: details.resumeMode,
        resumeId: details.resumeId,
        runtimeShell: details.runtimeShell && details.runtimeShell !== 'unknown' ? details.runtimeShell : (0, history_1.detectRuntimeShell)(fp),
    };
    return summary;
}
