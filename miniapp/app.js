const api = require("./utils/api");
const { APP_CONFIG, getApiBase, getEnvVersion } = require("./utils/config");

App({
  globalData: {
    visitorToken: "",
    userId: "",
    apiBase: getApiBase(),
    envVersion: getEnvVersion(),
    appName: APP_CONFIG.appName,
    shortName: APP_CONFIG.shortName,
  },

  onLaunch() {
    if (!this.globalData.apiBase) {
      console.warn("api base is empty");
    }

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
