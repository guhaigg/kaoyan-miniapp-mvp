const api = require("./utils/api");
const { APP_CONFIG, getApiBase, getEnvVersion } = require("./utils/config");

App({
  globalData: {
    visitorToken: "",
    userId: "",
    shadowUserId: "",
    linkedPortalUserId: "",
    userAccessToken: "",
    userRefreshToken: "",
    username: "",
    role: "user",
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
      linkedPortalUserId: this.globalData.linkedPortalUserId,
      username: this.globalData.username,
      role: this.globalData.role,
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

  applyPortalSession(payload = {}) {
    const linkedPortalUserId = payload.linked_portal_user_id || payload.user_id || "";
    this.setAuthState({
      userId: linkedPortalUserId,
      linkedPortalUserId,
      userAccessToken: payload.access_token || "",
      userRefreshToken: payload.refresh_token || "",
      username: payload.username || "",
      role: payload.role || "user",
      authMode: linkedPortalUserId && payload.access_token ? "portal_bound" : this.globalData.authMode,
    });
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
          const accessToken = data.access_token || "";
          const refreshToken = data.refresh_token || "";
          const linkedPortalUserId = data.linked_portal_user_id || "";
          const userId = linkedPortalUserId || data.user_id || "";
          const authMode = linkedPortalUserId && accessToken ? "portal_bound" : visitorToken ? "shadow" : "anonymous";
          this.setAuthState({
            visitorToken,
            userId,
            shadowUserId: data.shadow_user_id || data.user_id || "",
            linkedPortalUserId,
            userAccessToken: accessToken,
            userRefreshToken: refreshToken,
            username: data.username || "",
            role: data.role || "user",
            authMode,
            silentLoginError: "",
          });
          if (authMode === "portal_bound") {
            this.applyPortalSession(data);
          }
        } catch (err) {
          this.setAuthState({
            visitorToken: "",
            userId: "",
            shadowUserId: "",
            linkedPortalUserId: "",
            userAccessToken: "",
            userRefreshToken: "",
            username: "",
            role: "user",
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
          visitorToken: "",
          userId: "",
          shadowUserId: "",
          linkedPortalUserId: "",
          userAccessToken: "",
          userRefreshToken: "",
          username: "",
          role: "user",
          authReady: true,
          authMode: "anonymous",
          silentLoginError: String(err?.errMsg || "wx.login failed"),
        });
      },
    });
  },
});
