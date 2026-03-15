Page({
  data: {
    title: "状态",
    message: "请稍后再试",
  },

  onLoad(options) {
    this.setData({
      title: decodeURIComponent(options.title || "状态"),
      message: decodeURIComponent(options.message || "请稍后再试"),
    });
  },

  goBack() {
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    this.goHome();
  },

  goHome() {
    wx.reLaunch({ url: "/pages/home/index" });
  },
});
