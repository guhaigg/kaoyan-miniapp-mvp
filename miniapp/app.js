const api = require("./utils/api");

App({
  globalData: {
    visitorToken: "",
    userId: "",
    apiBase: "http://127.0.0.1:8000/api/v1",
  },

  onLaunch() {
    wx.login({
      success: async (res) => {
        if (!res.code) return;
        try {
          const data = await api.silentLogin(res.code);
          this.globalData.visitorToken = data.visitor_token || "";
          this.globalData.userId = data.user_id || "";
        } catch (err) {
          console.warn("silent login failed", err);
        }
      },
    });
  },
});

