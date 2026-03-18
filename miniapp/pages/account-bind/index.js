const api = require("../../utils/api");

function describeRole(role) {
  if (role === "admin") return "管理员";
  if (role === "premium") return "高级会员";
  return "普通用户";
}

Page({
  data: {
    bindCode: "",
    username: "",
    password: "",
    submitting: false,
    canBind: true,
    statusText: "当前微信身份尚未绑定网站账号。",
    linkedUsername: "",
    linkedPortalUserId: "",
    linkedRoleText: "",
    message: "",
    messageType: "success",
  },

  onShow() {
    this.syncBindingState();
  },

  syncBindingState() {
    const app = getApp();
    const { authMode, username, linkedPortalUserId, role } = app.globalData || {};
    const isBound = authMode === "portal_bound" && !!linkedPortalUserId;
    this.setData({
      canBind: !isBound,
      linkedUsername: username || "",
      linkedPortalUserId: linkedPortalUserId || "",
      linkedRoleText: describeRole(role || "user"),
      statusText: isBound ? "当前微信身份已绑定网站账号，可直接共享网站数据。" : "当前微信身份尚未绑定网站账号。",
    });
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value });
  },

  onBindCodeInput(e) {
    this.setData({ bindCode: e.detail.value });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value });
  },

  applyBindPayload(bindPayload) {
    const app = getApp();
    if (typeof app.applyPortalSession === "function") {
      app.applyPortalSession({
        ...bindPayload,
        linked_portal_user_id: bindPayload.user_id,
      });
    } else {
      app.setAuthState({
        userId: bindPayload.user_id,
        linkedPortalUserId: bindPayload.user_id,
        userAccessToken: bindPayload.access_token,
        userRefreshToken: bindPayload.refresh_token,
        username: bindPayload.username,
        role: bindPayload.role,
        authMode: "portal_bound",
      });
    }
    this.setData({
      bindCode: "",
      password: "",
      canBind: false,
      linkedUsername: bindPayload.username,
      linkedPortalUserId: bindPayload.user_id,
      linkedRoleText: describeRole(bindPayload.role),
      statusText: "当前微信身份已绑定网站账号，可直接共享网站数据。",
    });
  },

  async submitBindCode() {
    const app = getApp();
    const { bindCode, submitting } = this.data;
    if (submitting) return;
    if (!app?.globalData?.visitorToken) {
      this.setData({
        message: "当前没有可用的微信静默身份，请返回首页稍后重试。",
        messageType: "error",
      });
      return;
    }
    if (!bindCode.trim()) {
      this.setData({
        message: "请输入网站端生成的绑定码。",
        messageType: "error",
      });
      return;
    }

    this.setData({ submitting: true, message: "" });
    try {
      const bindPayload = await api.claimWechatBindCode(bindCode.trim());
      this.applyBindPayload(bindPayload);
      this.setData({
        message: "绑定成功，当前小程序已切换到主账号身份。",
        messageType: "success",
      });
    } catch (err) {
      this.setData({
        message: String(err?.detail || err?.message || err || "绑定失败"),
        messageType: "error",
      });
    } finally {
      this.setData({ submitting: false });
    }
  },

  async submitBind() {
    const app = getApp();
    const { username, password, submitting } = this.data;
    if (submitting) return;
    if (!app?.globalData?.visitorToken) {
      this.setData({
        message: "当前没有可用的微信静默身份，请返回首页稍后重试。",
        messageType: "error",
      });
      return;
    }
    if (!username.trim() || !password.trim()) {
      this.setData({
        message: "请输入网站用户名和密码。",
        messageType: "error",
      });
      return;
    }

    this.setData({ submitting: true, message: "" });
    try {
      const loginPayload = await api.loginUser(username.trim(), password);
      const bindPayload = await api.bindWechatAccount(loginPayload.access_token);
      this.applyBindPayload(bindPayload);
      this.setData({
        message: "绑定成功，当前小程序已切换到主账号身份。",
        messageType: "success",
      });
    } catch (err) {
      this.setData({
        message: String(err?.detail || err?.message || err || "绑定失败"),
        messageType: "error",
      });
    } finally {
      this.setData({ submitting: false });
    }
  },
});
