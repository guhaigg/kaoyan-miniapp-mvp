const APP_CONFIG = {
  appName: "格物简录",
  shortName: "格物简",
  manualApiBase: "",
  apiBaseByEnv: {
    develop: "https://api.gewujl.cloud/api/v1",
    trial: "https://api.gewujl.cloud/api/v1",
    release: "https://api.gewujl.cloud/api/v1",
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

module.exports = {
  APP_CONFIG,
  getApiBase,
  getEnvVersion,
};
