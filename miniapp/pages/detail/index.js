Page({
  data: {
    item: null,
  },

  onLoad(options) {
    try {
      const raw = decodeURIComponent(options.payload || "{}");
      const item = JSON.parse(raw);
      this.setData({ item });
    } catch (err) {
      wx.navigateTo({
        url: `/pages/status/index?title=${encodeURIComponent("详情解析失败")}&message=${encodeURIComponent(String(err))}`,
      });
    }
  },

  copySourceUrl() {
    const url = this.data.item?.source_url;
    if (!url) return;
    wx.setClipboardData({ data: url });
  },
});

