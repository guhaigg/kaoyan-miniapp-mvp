function safeDecode(raw, fallback) {
  if (typeof raw !== "string") {
    return fallback;
  }
  const value = raw.trim();
  if (!value) {
    return fallback;
  }
  try {
    const decoded = decodeURIComponent(value).trim();
    return decoded || fallback;
  } catch (error) {
    return value;
  }
}

Page({
  data: {
    title: "状态",
    message: "请稍后再试",
  },

  onLoad(options = {}) {
    this.setData({
      title: safeDecode(options.title, "状态"),
      message: safeDecode(options.message, "请稍后再试"),
    });
  },

  copyMessage() {
    const text = `${this.data.title}\n${this.data.message}`;
    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({
          title: "已复制",
          icon: "success",
        });
      },
      fail: () => {
        wx.showToast({
          title: "复制失败",
          icon: "none",
        });
      },
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
