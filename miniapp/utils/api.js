const { getApiBase } = require("./config");

function request(path, method = "GET", data = null) {
  const app = getApp();
  const token = app?.globalData?.visitorToken || "";
  const baseUrl = app?.globalData?.apiBase || getApiBase();
  const requestUrl = `${baseUrl}${path}`;

  return new Promise((resolve, reject) => {
    wx.request({
      url: requestUrl,
      method,
      data,
      header: {
        "Content-Type": "application/json",
        "X-Visitor-Token": token,
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
}

function silentLogin(code) {
  return request("/auth/silent-login", "POST", { code });
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
  searchAnnouncements,
  searchAdjustments,
};
