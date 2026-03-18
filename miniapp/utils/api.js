const { getApiBase } = require("./config");

function waitForAuthReady(timeoutMs = 800) {
  const app = getApp();
  if (!app || app.globalData?.authReady) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    let finished = false;
    let timer = null;
    let unsubscribe = null;
    const finish = () => {
      if (finished) return;
      finished = true;
      if (timer) clearTimeout(timer);
      if (typeof unsubscribe === "function") unsubscribe();
      resolve();
    };

    timer = setTimeout(finish, timeoutMs);
    if (typeof app.subscribeAuthStateChange === "function") {
      unsubscribe = app.subscribeAuthStateChange((snapshot) => {
        if (snapshot?.authReady) {
          finish();
        }
      });
    }
  });
}

function request(path, method = "GET", data = null, options = {}) {
  return waitForAuthReady().then(() => {
    const app = getApp();
    const visitorToken = app?.globalData?.visitorToken || "";
    const userToken = app?.globalData?.userAccessToken || "";
    const baseUrl = app?.globalData?.apiBase || getApiBase();
    const requestUrl = `${baseUrl}${path}`;
    const extraHeaders = options.headers || {};

    return new Promise((resolve, reject) => {
      wx.request({
        url: requestUrl,
        method,
        data,
        header: {
          "Content-Type": "application/json",
          "X-Visitor-Token": visitorToken,
          "X-User-Token": userToken,
          ...extraHeaders,
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(res.data);
            return;
          }
          reject(
            res.data || {
              code: res.statusCode,
              message: "服务返回异常状态码",
              detail: `HTTP ${res.statusCode} (${requestUrl})`,
            }
          );
        },
        fail: (err) => {
          const errMsg = typeof err?.errMsg === "string" ? err.errMsg.trim() : "";
          reject({
            code: "NETWORK_ERROR",
            message: "网络连接失败，请检查网络或代理设置",
            detail: errMsg
              ? `${errMsg}，目标地址：${requestUrl}`
              : `无法连接服务，目标地址：${requestUrl}`,
          });
        },
      });
    });
  });
}

function silentLogin(code) {
  return request("/auth/silent-login", "POST", { code });
}

function loginUser(username, password) {
  return request("/auth/login", "POST", { username, password });
}

function refreshUser(refreshToken) {
  return request("/auth/refresh", "POST", { refresh_token: refreshToken });
}

function bindWechatAccount(userAccessToken = "") {
  const headers = {};
  if (userAccessToken) {
    headers.Authorization = `Bearer ${userAccessToken}`;
  }
  return request("/auth/wechat/bind", "POST", {}, { headers });
}

function claimWechatBindCode(code) {
  return request("/auth/wechat/bind-code/claim", "POST", { code });
}

function searchAnnouncements(payload) {
  return request("/search/announcements", "POST", payload);
}

function searchAdjustments(payload) {
  return request("/search/adjustments", "POST", payload);
}

module.exports = {
  getApiBase,
  request,
  silentLogin,
  loginUser,
  refreshUser,
  bindWechatAccount,
  claimWechatBindCode,
  searchAnnouncements,
  searchAdjustments,
  waitForAuthReady,
};
