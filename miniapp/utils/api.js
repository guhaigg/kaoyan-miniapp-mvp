const { getApiBase, getApiFallbackBases } = require("./config");

function requestOnce(requestUrl, method, data, token) {
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

function isRetryableNetworkError(error) {
  const detail = typeof error?.detail === "string" ? error.detail.toLowerCase() : "";
  if (!detail) {
    return true;
  }
  return (
    detail.includes("err_connection_reset") ||
    detail.includes("ssl") ||
    detail.includes("timeout") ||
    detail.includes("network") ||
    detail.includes("request:fail")
  );
}

function request(path, method = "GET", data = null) {
  const app = getApp();
  const token = app?.globalData?.visitorToken || "";
  const primaryBase = app?.globalData?.apiBase || getApiBase();
  const candidateBases = [primaryBase, ...getApiFallbackBases(primaryBase)];
  const attemptedUrls = [];

  const run = async () => {
    let lastError = null;
    for (let i = 0; i < candidateBases.length; i += 1) {
      const baseUrl = candidateBases[i];
      const requestUrl = `${baseUrl}${path}`;
      attemptedUrls.push(requestUrl);
      try {
        const result = await requestOnce(requestUrl, method, data, token);
        if (app?.globalData) {
          app.globalData.apiBase = baseUrl;
        }
        return result;
      } catch (error) {
        lastError = error;
        const hasNext = i < candidateBases.length - 1;
        if (!(hasNext && error?.code === "NETWORK_ERROR" && isRetryableNetworkError(error))) {
          throw error;
        }
      }
    }
    throw (
      lastError || {
        code: "NETWORK_ERROR",
        message: "网络连接失败，请检查网络或代理设置",
      }
    );
  };

  return run().catch((error) => {
    if (error?.code === "NETWORK_ERROR") {
      return Promise.reject({
        ...error,
        detail: `${error?.detail || "网络连接失败"}，已尝试：${attemptedUrls.join(" | ")}`,
      });
    }
    return Promise.reject(error);
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
