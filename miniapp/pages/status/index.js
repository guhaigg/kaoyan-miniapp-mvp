Page({
  data: {
    title: "状态",
    message: "",
  },

  onLoad(options) {
    this.setData({
      title: decodeURIComponent(options.title || "状态"),
      message: decodeURIComponent(options.message || ""),
    });
  },
});

