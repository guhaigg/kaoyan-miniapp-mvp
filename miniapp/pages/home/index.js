Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
    accessModeText: "正在初始化访问身份...",
  },

  onLoad() {
    const app = getApp();
    if (typeof app.subscribeAuthStateChange === "function") {
      this._unsubscribeAuthListener = app.subscribeAuthStateChange(() => {
        this.syncAccessModeText();
      });
    }
  },

  onShow() {
    this.syncAccessModeText();
  },

  onUnload() {
    if (typeof this._unsubscribeAuthListener === "function") {
      this._unsubscribeAuthListener();
      this._unsubscribeAuthListener = null;
    }
  },

  syncAccessModeText() {
    const app = getApp();
    const { authReady, authMode, silentLoginError } = app.globalData || {};
    let accessModeText = "正在初始化访问身份...";
    if (authReady) {
      accessModeText = authMode === "shadow" ? "当前为静默影子账户访问模式" : "当前为匿名访问模式";
      if (silentLoginError) {
        accessModeText += "；静默登录失败，已自动降级为可浏览模式";
      }
    }
    this.setData({ accessModeText });
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
