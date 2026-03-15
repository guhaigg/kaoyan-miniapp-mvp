const { goStatus } = require("../../utils/status");

function normalizeItem(input) {
  const raw = input && typeof input === "object" && !Array.isArray(input) ? input : {};
  const normalizeText = (value, fallback = "") => {
    if (typeof value !== "string") return fallback;
    const trimmed = value.trim();
    return trimmed || fallback;
  };

  return {
    title: normalizeText(raw.title, "未命名信息"),
    school_name: normalizeText(raw.school_name),
    published_at: normalizeText(raw.published_at),
    category: normalizeText(raw.category),
    source_type: normalizeText(raw.source_type),
    major: normalizeText(raw.major),
    region: normalizeText(raw.region),
    summary: normalizeText(raw.summary),
    source_url: normalizeText(raw.source_url),
  };
}

Page({
  data: {
    item: null,
  },

  onLoad(options) {
    try {
      const raw = decodeURIComponent(options.payload || "{}");
      const parsed = JSON.parse(raw);
      const item = normalizeItem(parsed);
      this.setData({ item });
    } catch (err) {
      goStatus("详情解析失败", err, "页面参数异常，请返回后重试");
    }
  },

  copySourceUrl() {
    const url = this.data.item?.source_url;
    if (!url) return;
    wx.setClipboardData({ data: url });
  },
});
