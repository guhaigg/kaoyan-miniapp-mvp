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
    authReady: false,
    authMode: "anonymous",
    silentLoginError: "",
  },

  onLaunch() {
    if (!this.globalData.apiBase) {
      console.warn("api base is empty");
    }

    wx.login({
      success: async (res) => {
        if (!res.code) {
          this.globalData.authReady = true;
          this.globalData.authMode = "anonymous";
          return;
        }
        try {
          const data = await api.silentLogin(res.code);
          this.globalData.visitorToken = data.visitor_token || "";
          this.globalData.userId = data.user_id || "";
          this.globalData.authMode = this.globalData.visitorToken ? "shadow" : "anonymous";
        } catch (err) {
          this.globalData.authMode = "anonymous";
          this.globalData.silentLoginError = String(err?.detail || err?.message || err || "");
          console.warn("silent login failed", err);
        } finally {
          this.globalData.authReady = true;
        }
      },
      fail: () => {
        this.globalData.authReady = true;
        this.globalData.authMode = "anonymous";
      },
    });
  },
});
