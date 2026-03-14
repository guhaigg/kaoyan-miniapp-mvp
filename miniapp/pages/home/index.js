Page({
  data: {
    schoolName: "",
    keywords: "",
    major: "",
    region: "",
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

