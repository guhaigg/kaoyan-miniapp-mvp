Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
    accessModeText: "正在初始化访问身份...",
    buildId: "",
    envVersion: "",
  },

  onShow() {
    const app = getApp();
    const { authReady, authMode, buildId, envVersion } = app.globalData || {};
    let accessModeText = "正在初始化访问身份...";
    if (authReady) {
      accessModeText = authMode === "shadow" ? "当前为静默影子账户访问模式" : "当前为匿名访问模式";
    }
    this.setData({
      accessModeText,
      buildId: buildId || "",
      envVersion: envVersion || "",
    });
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

  goAnnouncements() {
    const { schoolName, keywords } = this.data;
    wx.navigateTo({
      url: `/pages/announcements/index?schoolName=${encodeURIComponent(schoolName)}&keywords=${encodeURIComponent(keywords)}`,
    });
  },

  goAdjustments() {
    const { schoolName, keywords, major, region } = this.data;
    wx.navigateTo({
      url:
        `/pages/adjustments/index?schoolName=${encodeURIComponent(schoolName)}` +
        `&keywords=${encodeURIComponent(keywords)}&major=${encodeURIComponent(major)}&region=${encodeURIComponent(region)}`,
    });
  },
});
