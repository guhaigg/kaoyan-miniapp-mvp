const api = require("../../utils/api");

Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
    loading: false,
    refresh: false,
    items: [],
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
      this.setData({ items: result.items || [] });
      if (this.data.refresh && result.refresh_job_id) {
        wx.showToast({ title: "补抓任务已提交", icon: "none" });
        this.pollJob(result.refresh_job_id, 0);
      }
    } catch (err) {
      wx.navigateTo({
        url: `/pages/status/index?title=${encodeURIComponent("查询失败")}&message=${encodeURIComponent(JSON.stringify(err))}`,
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  openDetail(e) {
    const item = e.currentTarget.dataset.item;
    wx.navigateTo({ url: `/pages/detail/index?payload=${encodeURIComponent(JSON.stringify(item))}` });
  },

  async pollJob(jobId, attempt) {
    if (attempt > 12) {
      wx.showToast({ title: "补抓超时，请稍后重查", icon: "none" });
      return;
    }
    try {
      const status = await api.getJobStatus(jobId);
      if (status.status === "completed") {
        wx.showToast({ title: "补抓完成", icon: "success" });
        const result = await api.searchAdjustments({
          school_name: this.data.schoolName || null,
          keywords: this.data.keywords || null,
          major: this.data.major || null,
          region: this.data.region || null,
          page: 1,
          page_size: 20,
          refresh: false,
        });
        this.setData({ items: result.items || [] });
        return;
      }
      if (status.status === "failed") {
        wx.showToast({ title: "补抓失败", icon: "none" });
        return;
      }
      setTimeout(() => this.pollJob(jobId, attempt + 1), 1500);
    } catch (_err) {
      setTimeout(() => this.pollJob(jobId, attempt + 1), 1500);
    }
  },
});
