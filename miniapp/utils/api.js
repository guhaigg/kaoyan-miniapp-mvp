const DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1";

function getBaseUrl() {
  const app = getApp();
  return app?.globalData?.apiBase || DEFAULT_BASE_URL;
}

function request(path, method = "GET", data = null) {
  const app = getApp();
  const token = app?.globalData?.visitorToken || "";
  const baseUrl = getBaseUrl();

  return new Promise((resolve, reject) => {
    wx.request({
      url: `${baseUrl}${path}`,
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
        reject(res.data || { message: "Request failed" });
      },
      fail: reject,
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
  BASE_URL: DEFAULT_BASE_URL,
  request,
  silentLogin,
  searchAnnouncements,
  searchAdjustments,
};
