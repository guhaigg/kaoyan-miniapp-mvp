const api = require("../../utils/api");
const { goStatus } = require("../../utils/status");

Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
    loading: false,
    refresh: false,
    items: [],
    lastQueryAt: "",
  },

  onLoad(options) {
    this.setData({
      schoolName: decodeURIComponent(options.schoolName || ""),
      keywords: decodeURIComponent(options.keywords || ""),
      major: decodeURIComponent(options.major || ""),
      region: decodeURIComponent(options.region || ""),
    });
    this.runQuery();
  },

  onSchoolInput(e) {
    this.setData({ schoolName: e.detail.value });
  },
  onKeywordsInput(e) {
    this.setData({ keywords: e.detail.value });
  },
  onMajorInput(e) {
    this.setData({ major: e.detail.value });
  },
  onRegionInput(e) {
    this.setData({ region: e.detail.value });
  },
  onRefreshChange(e) {
    this.setData({ refresh: !!e.detail.value.length });
  },

  async runQuery() {
    this.setData({ loading: true });
    try {
      const result = await api.searchAdjustments({
        school_name: this.data.schoolName || null,
        keywords: this.data.keywords || null,
        major: this.data.major || null,
        region: this.data.region || null,
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
      goStatus("调剂查询失败", err, "请稍后重试，或缩小查询范围");
    } finally {
      this.setData({ loading: false });
    }
  },

  openDetail(e) {
    const item = e.currentTarget.dataset.item;
    if (!item) {
      goStatus("详情加载失败", null, "未找到可查看的数据，请刷新后重试");
      return;
    }
    wx.navigateTo({ url: `/pages/detail/index?payload=${encodeURIComponent(JSON.stringify(item))}` });
  },
});
