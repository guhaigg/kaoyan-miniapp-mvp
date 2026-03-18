const api = require("../../utils/api");
const { goStatus } = require("../../utils/status");

Page({
  data: {
    schoolName: "",
    keywords: "",
    loading: false,
    refresh: false,
    items: [],
    lastQueryAt: "",
  },

  onLoad(options) {
    this.setData({
      schoolName: decodeURIComponent(options.schoolName || ""),
      keywords: decodeURIComponent(options.keywords || ""),
    });
    this.runQuery();
  },

  onSchoolInput(e) {
    this.setData({ schoolName: e.detail.value });
  },

  onKeywordsInput(e) {
    this.setData({ keywords: e.detail.value });
  },

  onRefreshChange(e) {
    this.setData({ refresh: !!e.detail.value.length });
  },

  async runQuery() {
    this.setData({ loading: true });
    try {
      const result = await api.searchAnnouncements({
        school_name: this.data.schoolName || null,
        keywords: this.data.keywords || null,
        page: 1,
        page_size: 20,
        refresh: this.data.refresh,
      });
      const items = Array.isArray(result.items) ? result.items : [];
      this.setData({
        items,
        lastQueryAt: new Date().toLocaleString(),
      });
    } catch (err) {
      goStatus("公告查询失败", err, "请稍后重试，或缩小查询范围", { action: "back", source: "announcements" });
    } finally {
      this.setData({ loading: false });
    }
  },

  openDetail(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) {
      goStatus("详情加载失败", null, "未找到可查看的数据，请刷新后重试", { action: "back", source: "announcements" });
      return;
    }
    wx.navigateTo({ url: `/pages/detail/index?payload=${encodeURIComponent(JSON.stringify(item))}` });
  },
});
