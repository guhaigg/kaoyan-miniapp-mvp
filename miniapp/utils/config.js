const APP_CONFIG = {
  appName: "格物简录",
  shortName: "格物简",
  manualApiBase: "",
  apiBaseByEnv: {
    develop: "https://api.gewujl.cloud/api/v1",
    trial: "https://api.gewujl.cloud/api/v1",
    release: "https://api.gewujl.cloud/api/v1",
  },
  apiFallbackByEnv: {
    develop: ["https://gewujl.cloud/api/v1"],
    trial: ["https://gewujl.cloud/api/v1"],
    release: ["https://gewujl.cloud/api/v1"],
  },
};

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
  if (APP_CONFIG.manualApiBase) {
    return APP_CONFIG.manualApiBase;
  }

  const envVersion = getEnvVersion();
  return APP_CONFIG.apiBaseByEnv[envVersion] || APP_CONFIG.apiBaseByEnv.develop;
}

function getApiFallbackBases(primaryBase = "") {
  const envVersion = getEnvVersion();
  const configured =
    APP_CONFIG.apiFallbackByEnv[envVersion] || APP_CONFIG.apiFallbackByEnv.develop || [];

  const seen = new Set();
  const result = [];
  for (const base of configured) {
    if (typeof base !== "string") {
      continue;
    }
    const trimmed = base.trim();
    if (!trimmed || trimmed === primaryBase || seen.has(trimmed)) {
      continue;
    }
    seen.add(trimmed);
    result.push(trimmed);
  }

  return result;
}

module.exports = {
  APP_CONFIG,
  getApiBase,
  getApiFallbackBases,
  getEnvVersion,
};
