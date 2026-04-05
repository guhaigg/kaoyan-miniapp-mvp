"use strict";
const history_1 = require("./history");
const indexer_1 = require("./indexer");
const log_1 = require("./log");
const settings_1 = require("./settings");
const parser_2 = require("./agentSessions/gemini/parser");
const electron_1 = require("electron");
electron_1.ipcMain.handle('history.list', async (_e, args) => {
    try {
        const all = (0, indexer_1.getIndexedSummaries)();
        const needles = [];
        const geminiHashNeedles = new Set();
        const filtered = needles.length === 0
            ? all
            : all.filter((s) => {
                if (needles.some((n) => startsWithBoundary(s.dirKey, n)))
                    return true;
                if (s.providerId === 'gemini' && geminiHashNeedles.size > 0) {
                    const hs = String(s?.projectHash || '').trim().toLowerCase();
                    const hp = (0, parser_2.extractGeminiProjectHashFromPath)(String(s.filePath || ''));
                    const h = hs || hp || '';
                    if (h && geminiHashNeedles.has(h))
                        return true;
                }
                return false;
            });
            const sorted = filtered.sort((a, b) => b.date - a.date);
            const offset = Math.max(0, Number(args.offset || 0));
            const end = args.limit ? offset + Number(args.limit) : undefined;
            const sliced = sorted.slice(offset, end);
            const mapped = sliced.map((x) => ({
                providerId: x.providerId || "codex",
                id: x.id,
                title: x.title,
                date: x.date,
                filePath: x.filePath,
                rawDate: x.rawDate,
                preview: x.preview,
                projectHash: x.projectHash,
                resumeMode: x.resumeMode,
                resumeId: x.resumeId,
                runtimeShell: x.runtimeShell,
            }));
            return { ok: true, sessions: mapped };
    }
    catch (e) {
        return { ok: false, error: String(e) };
    }
});
