const { getApiBase, getApiBaseCandidates } = require("./config");

function dedupeBaseUrls(urls) {
  const normalized = Array.isArray(urls)
    ? urls.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
  return Array.from(new Set(normalized));
}

function requestOnce(requestUrl, method, data, token) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: requestUrl,
      method,
      data,
      timeout: 12000,
      enableHttp2: false,
      enableQuic: false,
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
        const errno = typeof err?.errno === "number" ? `，errno:${err.errno}` : "";
        reject({
          code: "NETWORK_ERROR",
          message: "网络连接失败，请检查网络或代理设置",
          detail: errMsg
            ? `${errMsg}${errno}，目标地址：${requestUrl}`
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

function isDomainListError(error) {
  const detail = typeof error?.detail === "string" ? error.detail.toLowerCase() : "";
  return detail.includes("url not in domain list");
}

function request(path, method = "GET", data = null) {
  const app = getApp();
  const token = app?.globalData?.visitorToken || "";
  const configuredBases = dedupeBaseUrls(
    app?.globalData?.apiBaseCandidates?.length
      ? app.globalData.apiBaseCandidates
      : getApiBaseCandidates()
  );
  const primaryBase = app?.globalData?.apiBase || configuredBases[0] || getApiBase();
  const baseCandidates = dedupeBaseUrls([primaryBase, ...configuredBases]);
  const attemptedUrls = [];

  const run = async () => {
    let lastError = null;
    let primaryNetworkError = null;

    for (const baseUrl of baseCandidates) {
      const requestUrl = `${baseUrl}${path}`;
      for (let attempt = 1; attempt <= 3; attempt += 1) {
        attemptedUrls.push(requestUrl);
        try {
          const result = await requestOnce(requestUrl, method, data, token);
          if (app?.globalData) {
            app.globalData.apiBase = baseUrl;
            app.globalData.apiBaseCandidates = baseCandidates;
          }
          return result;
        } catch (error) {
          lastError = error;
          const isNetworkError =
            error?.code === "NETWORK_ERROR" && isRetryableNetworkError(error);
          const domainListError = isDomainListError(error);

          if (baseUrl === primaryBase && isNetworkError && !domainListError) {
            primaryNetworkError = error;
          }

          if (isNetworkError && !domainListError && attempt < 3) {
            continue;
          }
          break;
        }
      }
    }

    const finalError =
      primaryNetworkError && isDomainListError(lastError) ? primaryNetworkError : lastError;
    if (finalError) {
      throw finalError;
    }

    throw {
      code: "NETWORK_ERROR",
      message: "网络连接失败，请检查网络或代理设置",
      detail: `无法连接服务，目标地址：${baseCandidates.map((base) => `${base}${path}`).join(" | ")}`,
    };
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
