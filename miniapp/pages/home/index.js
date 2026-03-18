Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
    accessModeText: "正在初始化访问身份...",
    bindActionText: "绑定网站账号",
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
    const { authReady, authMode, silentLoginError, username } = app.globalData || {};
    let accessModeText = "正在初始化访问身份...";
    let bindActionText = "绑定网站账号";
    if (authReady) {
      if (authMode === "portal_bound") {
        accessModeText = username
          ? `当前已绑定网站账号：${username}`
          : "当前已绑定网站账号，可跨端同步收藏、监控和会员权益";
        bindActionText = "查看绑定状态";
      } else if (authMode === "shadow") {
        accessModeText = "当前为静默影子账户访问模式";
        bindActionText = "绑定网站账号";
      } else {
        accessModeText = "当前为匿名访问模式";
        bindActionText = "等待微信登录";
      }
      if (silentLoginError) {
        accessModeText += "；静默登录失败，已自动降级为可浏览模式";
      }
    }
    this.setData({ accessModeText, bindActionText });
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

  goBindAccount() {
    wx.navigateTo({
      url: "/pages/account-bind/index",
    });
  },
});
