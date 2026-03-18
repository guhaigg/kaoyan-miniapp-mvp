Page({
  data: {
    title: "状态",
    message: "请稍后再试",
    action: "",
    actionText: "",
    source: "",
    primaryActionText: "返回首页",
    showHomeShortcut: false,
  },

  onLoad(options) {
    this.setData({
      title: decodeURIComponent(options.title || "状态"),
      message: decodeURIComponent(options.message || "请稍后再试"),
      action: decodeURIComponent(options.action || ""),
      actionText: decodeURIComponent(options.actionText || ""),
      source: decodeURIComponent(options.source || ""),
    });
    this.syncActionState();
  },

  onShow() {
    this.syncActionState();
  },

  resolvePrimaryAction() {
    const pages = getCurrentPages();
    if (this.data.action === "home") {
      return { handler: "goHome", text: this.data.actionText || "返回首页" };
    }
    if (this.data.action === "back" && pages.length > 1) {
      return { handler: "goBack", text: this.data.actionText || "返回上一页" };
    }
    if (pages.length > 1) {
      return { handler: "goBack", text: this.data.actionText || "返回上一页" };
    }
    return { handler: "goHome", text: this.data.actionText || "返回首页" };
  },

  syncActionState() {
    const action = this.resolvePrimaryAction();
    this.setData({
      primaryActionText: action.text,
      showHomeShortcut: action.handler !== "goHome",
    });
  },

  handlePrimaryAction() {
    const action = this.resolvePrimaryAction();
    if (action.handler === "goBack") {
      this.goBack();
      return;
    }
    this.goHome();
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
