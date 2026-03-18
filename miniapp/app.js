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

  _authListeners: [],

  subscribeAuthStateChange(listener) {
    if (typeof listener !== "function") {
      return () => {};
    }
    this._authListeners.push(listener);
    return () => {
      this._authListeners = this._authListeners.filter((item) => item !== listener);
    };
  },

  notifyAuthStateChange() {
    const snapshot = {
      authReady: this.globalData.authReady,
      authMode: this.globalData.authMode,
      silentLoginError: this.globalData.silentLoginError,
      visitorToken: this.globalData.visitorToken,
      userId: this.globalData.userId,
    };
    this._authListeners.forEach((listener) => {
      try {
        listener(snapshot);
      } catch (err) {
        console.warn("auth listener failed", err);
      }
    });
  },

  setAuthState(patch) {
    Object.assign(this.globalData, patch);
    this.notifyAuthStateChange();
  },

  onLaunch() {
    if (!this.globalData.apiBase) {
      console.warn("api base is empty");
    }

    wx.login({
      success: async (res) => {
        if (!res.code) {
          this.setAuthState({
            authReady: true,
            authMode: "anonymous",
            silentLoginError: "wx.login succeeded but no code returned",
          });
          return;
        }
        try {
          const data = await api.silentLogin(res.code);
          const visitorToken = data.visitor_token || "";
          this.setAuthState({
            visitorToken,
            userId: data.user_id || "",
            authMode: visitorToken ? "shadow" : "anonymous",
            silentLoginError: "",
          });
        } catch (err) {
          this.setAuthState({
            authMode: "anonymous",
            silentLoginError: String(err?.detail || err?.message || err || ""),
          });
          console.warn("silent login failed", err);
        } finally {
          this.setAuthState({ authReady: true });
        }
      },
      fail: (err) => {
        this.setAuthState({
          authReady: true,
          authMode: "anonymous",
          silentLoginError: String(err?.errMsg || "wx.login failed"),
        });
      },
    });
  },
});
