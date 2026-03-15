const APP_CONFIG = {
  appName: "格物简录",
  shortName: "格物简",
  buildId: "20260315-1830",
  manualApiBase: "",
  manualApiBaseCandidates: [],
  apiBaseByEnv: {
    develop: [
      "https://api.gewujl.cloud/api/v1",
      "https://gewujl.cloud/api/v1",
      "https://www.gewujl.cloud/api/v1",
    ],
    trial: [
      "https://api.gewujl.cloud/api/v1",
      "https://gewujl.cloud/api/v1",
      "https://www.gewujl.cloud/api/v1",
    ],
    release: [
      "https://api.gewujl.cloud/api/v1",
      "https://gewujl.cloud/api/v1",
      "https://www.gewujl.cloud/api/v1",
    ],
  },
};

function normalizeApiBaseList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item || "").trim()).filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function uniqueApiBaseList(value) {
  return Array.from(new Set(normalizeApiBaseList(value)));
}

function getEnvVersion() {
  if (typeof wx === "undefined" || typeof wx.getAccountInfoSync !== "function") {
    return "develop";
  }

  try {
    return wx.getAccountInfoSync()?.miniProgram?.envVersion || "develop";
  } catch (error) {
    return "develop";
  }
}

function getApiBase() {
  return getApiBaseCandidates()[0] || "";
}

function getApiBaseCandidates() {
  if (APP_CONFIG.manualApiBase) {
    return uniqueApiBaseList([APP_CONFIG.manualApiBase, ...APP_CONFIG.manualApiBaseCandidates]);
  }

  const envVersion = getEnvVersion();
  const envConfigured = APP_CONFIG.apiBaseByEnv[envVersion] || APP_CONFIG.apiBaseByEnv.develop;
  return uniqueApiBaseList(envConfigured);
}

module.exports = {
  APP_CONFIG,
  getApiBase,
  getApiBaseCandidates,
  getEnvVersion,
};
