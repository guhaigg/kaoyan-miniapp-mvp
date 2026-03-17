(() => {
  if (window.__GW_APP_SHELL_LOADED__) return;
  window.__GW_APP_SHELL_LOADED__ = true;

  const API_BASE = "https://api.gewujl.cloud/api/v1";
  let cleanupCurrentPage = null;

  function byId(id) {
    return document.getElementById(id);
  }

  function esc(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  function fmtDate(value) {
    if (!value) return "未知时间";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString("zh-CN", { hour12: false });
  }

  function ensureBrandElements() {
    const iconPath = "/assets/brand/gw-mark.svg";
    const navBrand = document.querySelector('#navbar a[href="/"] .flex.flex-row');
    if (navBrand && !navBrand.querySelector("img[data-gw-logo]")) {
      const oldIcon = navBrand.querySelector("svg");
      if (oldIcon) oldIcon.remove();
      Array.from(navBrand.childNodes).forEach((node) => {
        if (node.nodeType === 3) node.textContent = "";
      });
      const logo = document.createElement("img");
      logo.src = iconPath;
      logo.alt = "GW";
      logo.setAttribute("data-gw-logo", "1");
      logo.style.width = "1.55rem";
      logo.style.height = "1.55rem";
      logo.style.borderRadius = "0.4rem";
      logo.style.marginRight = "0.5rem";
      logo.style.marginBottom = "0.1rem";
      navBrand.appendChild(logo);
      navBrand.appendChild(document.createTextNode(" GeWuJian"));
    }

    const currentIcon = document.querySelector('link[rel~="icon"][href="' + iconPath + '"]');
    if (!currentIcon) {
      document.querySelectorAll('link[rel~="icon"]').forEach((el) => el.remove());
      const icon = document.createElement("link");
      icon.rel = "icon";
      icon.type = "image/svg+xml";
      icon.href = iconPath;
      document.head.appendChild(icon);
    }
  }

  function initQueryPage() {
    const queryType = byId("queryType");
    const btnSearch = byId("btnSearch");
    const btnClear = byId("btnClear");
    const resultCards = byId("resultCards");
    if (!queryType || !btnSearch || !btnClear || !resultCards) return null;

    const handlers = [];
    let toastTimer = 0;

    const year = byId("year");
    if (year) year.textContent = String(new Date().getFullYear());

    function showToast(message, type = "") {
      const el = byId("toast");
      if (!el) return;
      el.textContent = message;
      el.classList.remove("ok", "error");
      if (type) el.classList.add(type);
      el.classList.add("show");
      window.clearTimeout(toastTimer);
      toastTimer = window.setTimeout(() => el.classList.remove("show"), 2200);
    }

    function toggleAdjustFields() {
      const isAdjust = queryType.value === "adjustments";
      const majorWrap = byId("majorWrap");
      const regionWrap = byId("regionWrap");
      if (majorWrap) majorWrap.style.display = isAdjust ? "" : "none";
      if (regionWrap) regionWrap.style.display = isAdjust ? "" : "none";
    }

    function renderItems(items) {
      if (!Array.isArray(items) || !items.length) {
        resultCards.innerHTML =
          "<article class='result-card'><p>未匹配到确切坐标，请尝试提取核心关键词。</p></article>";
        return;
      }

      resultCards.innerHTML = items
        .map((item) => {
          const source = item.source_url
            ? `<a href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">查看来源原文</a>`
            : "<span>暂无来源链接</span>";
          return `<article class="result-card">
            <h4>${esc(item.title || "未命名信息")}</h4>
            <p>${esc(item.summary || "暂无摘要")}</p>
            <div class="tag-row">
              <span class="tag">${esc(item.school_name || "未知院校")}</span>
              <span class="tag">${esc(item.major || "未标注专业")}</span>
              <span class="tag">${esc(item.region || "未标注地区")}</span>
              <span class="tag">${esc(fmtDate(item.published_at))}</span>
            </div>
            <p>${source}</p>
          </article>`;
        })
        .join("");
    }

    async function runSearch() {
      const endpoint =
        queryType.value === "adjustments"
          ? "/search/adjustments"
          : "/search/announcements";

      const payload = {
        school_name: (byId("schoolName")?.value || "").trim() || null,
        keywords: (byId("keywords")?.value || "").trim() || null,
        page: 1,
        page_size: Number(byId("pageSize")?.value || 20),
        refresh: false,
      };

      if (queryType.value === "adjustments") {
        payload.major = (byId("major")?.value || "").trim() || null;
        payload.region = (byId("region")?.value || "").trim() || null;
      }

      const resultMeta = byId("resultMeta");
      const resultHint = byId("resultHint");
      if (resultMeta) {
        resultMeta.textContent = "正在重构数据卡片...";
        resultMeta.classList.add("loading");
      }
      btnSearch.disabled = true;
      btnSearch.textContent = "检索中...";

      try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json();

        if (!response.ok) {
          if (resultMeta) resultMeta.textContent = `查询失败（${response.status}）`;
          if (resultHint) resultHint.textContent = "数据源响应超时，请稍后重连。";
          resultCards.innerHTML = "";
          showToast("数据源响应超时，请稍后重连。", "error");
          return;
        }

        const total = Number(data.total || 0);
        const mode = data.mode || "-";
        const items = Array.isArray(data.items) ? data.items : [];

        const sideTotal = byId("sideTotal");
        const sideMode = byId("sideMode");
        if (sideTotal) sideTotal.textContent = String(total);
        if (sideMode) sideMode.textContent = String(mode);
        if (resultMeta) resultMeta.textContent = `共 ${total} 条，当前显示 ${items.length} 条`;
        if (resultHint) resultHint.textContent = "数据已重构，可继续细化筛选条件。";
        renderItems(items);
        showToast("卡片已归档。", "ok");
      } catch (error) {
        if (resultMeta) resultMeta.textContent = "网络异常，请稍后重试。";
        if (resultHint) resultHint.textContent = String(error);
        resultCards.innerHTML = "";
        showToast("数据源响应超时，请稍后重连。", "error");
      } finally {
        if (resultMeta) resultMeta.classList.remove("loading");
        btnSearch.disabled = false;
        btnSearch.textContent = "执行查询";
      }
    }

    function clearQuery() {
      const defaults = [
        ["queryType", "announcements"],
        ["pageSize", "20"],
        ["schoolName", ""],
        ["keywords", ""],
        ["major", ""],
        ["region", ""],
      ];
      defaults.forEach(([id, value]) => {
        const el = byId(id);
        if (el) el.value = value;
      });

      toggleAdjustFields();
      const sideTotal = byId("sideTotal");
      const sideMode = byId("sideMode");
      const resultMeta = byId("resultMeta");
      const resultHint = byId("resultHint");
      if (sideTotal) sideTotal.textContent = "-";
      if (sideMode) sideMode.textContent = "-";
      if (resultMeta) resultMeta.textContent = "条件已重置。";
      if (resultHint) resultHint.textContent = "可重新定义关键词后再次查询。";
      resultCards.innerHTML = "";
    }

    async function loadPreview() {
      const previewList = byId("previewList");
      if (!previewList) return;
      try {
        const response = await fetch(`${API_BASE}/search/announcements`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page: 1, page_size: 3, refresh: false }),
        });
        const data = await response.json();
        const items = Array.isArray(data.items) ? data.items : [];
        if (!response.ok || !items.length) {
          previewList.innerHTML = "<li>暂无最新公告。底层探针正在持续观测。</li>";
          return;
        }

        previewList.innerHTML = items
          .map((item) => {
            const title = esc(item.title || "未命名信息");
            const school = esc(item.school_name || "未知院校");
            const dateText = esc(fmtDate(item.published_at));
            if (!item.source_url) return `<li>${title} · ${school} · ${dateText}</li>`;
            return `<li><a href="${esc(item.source_url)}" target="_blank" rel="noopener noreferrer">${title}</a> · ${school} · ${dateText}</li>`;
          })
          .join("");
      } catch {
        previewList.innerHTML = "<li>数据源响应超时，请稍后重连。</li>";
      }
    }

    function onKeydown(event) {
      if (event.key === "Enter") runSearch();
    }

    queryType.addEventListener("change", toggleAdjustFields);
    btnSearch.addEventListener("click", runSearch);
    btnClear.addEventListener("click", clearQuery);
    handlers.push(() => queryType.removeEventListener("change", toggleAdjustFields));
    handlers.push(() => btnSearch.removeEventListener("click", runSearch));
    handlers.push(() => btnClear.removeEventListener("click", clearQuery));

    ["schoolName", "keywords", "major", "region"].forEach((id) => {
      const input = byId(id);
      if (!input) return;
      input.addEventListener("keydown", onKeydown);
      handlers.push(() => input.removeEventListener("keydown", onKeydown));
    });

    toggleAdjustFields();
    loadPreview();
    runSearch();

    return () => {
      handlers.forEach((off) => off());
      window.clearTimeout(toastTimer);
    };
  }

  function initRegisterPage() {
    const tabRegister = byId("tabRegister");
    const tabLogin = byId("tabLogin");
    if (!tabRegister || !tabLogin) return null;

    const handlers = [];

    function setStatus(el, text, type = "") {
      if (!el) return;
      el.textContent = text;
      el.classList.remove("ok", "error", "loading");
      if (type) el.classList.add(type);
    }

    function switchTab(tab) {
      const isRegister = tab === "register";
      tabRegister.classList.toggle("active", isRegister);
      tabLogin.classList.toggle("active", !isRegister);
      byId("panelRegister")?.classList.toggle("active", isRegister);
      byId("panelLogin")?.classList.toggle("active", !isRegister);
    }

    function formatTTL(seconds) {
      const total = Number(seconds || 0);
      if (!Number.isFinite(total) || total <= 0) return "--";
      const days = Math.floor(total / 86400);
      const hours = Math.floor((total % 86400) / 3600);
      if (days > 0) return `${days}天${hours}小时`;
      return `${Math.max(1, Math.floor(total / 60))}分钟`;
    }

    function formatDateTime(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "--";
      return date.toLocaleString("zh-CN", { hour12: false });
    }

    function maskUserId(userId) {
      if (!userId) return "";
      const value = String(userId);
      if (value.length < 12) return value;
      return `${value.slice(0, 8)}...${value.slice(-6)}`;
    }

    function updateSessionPanel({
      username = "未登录",
      state = "未校验",
      expireAt = 0,
      expireIn = 0,
      checkedAt = 0,
      summary = "",
    }) {
      const sessionUser = byId("sessionUser");
      const sessionState = byId("sessionState");
      const sessionExpire = byId("sessionExpire");
      const sessionChecked = byId("sessionChecked");
      const sessionView = byId("sessionView");

      if (sessionUser) sessionUser.textContent = username;
      if (sessionState) sessionState.textContent = state;
      if (sessionExpire) {
        sessionExpire.textContent =
          expireAt > 0
            ? `${formatDateTime(expireAt)}（约${formatTTL(expireIn)}）`
            : "--";
      }
      if (sessionChecked) sessionChecked.textContent = checkedAt > 0 ? formatDateTime(checkedAt) : "--";
      if (sessionView) {
        sessionView.textContent =
          summary || "登录后会在这里显示状态摘要，不展示敏感技术字段。";
      }
    }

    function saveUserSession(payload) {
      const now = Date.now();
      const expireIn = Number(payload.expires_in || 0);
      const expireAt = expireIn > 0 ? now + expireIn * 1000 : 0;
      localStorage.setItem("gw_user_token", payload.access_token || "");
      localStorage.setItem("gw_user_name", payload.username || "");
      localStorage.setItem("gw_user_id", payload.user_id || "");
      localStorage.setItem("gw_access_expire_at", String(expireAt));
      localStorage.setItem("gw_access_expire_in", String(expireIn));
      updateSessionPanel({
        username: payload.username || "未命名用户",
        state: "已登录",
        expireAt,
        expireIn,
        checkedAt: now,
        summary: `登录成功，会话已建立。用户标识：${maskUserId(payload.user_id)}`,
      });
    }

    function clearUserSession() {
      localStorage.removeItem("gw_user_token");
      localStorage.removeItem("gw_user_name");
      localStorage.removeItem("gw_user_id");
      localStorage.removeItem("gw_access_expire_at");
      localStorage.removeItem("gw_access_expire_in");
      updateSessionPanel({
        username: "未登录",
        state: "未校验",
        summary: "尚未建立会话，请先登录。",
      });
    }

    async function register() {
      const username = (byId("regUsername")?.value || "").trim();
      const password = byId("regPassword")?.value || "";
      const nickname = (byId("regNickname")?.value || "").trim();
      const statusEl = byId("registerStatus");

      if (!username || !password) {
        setStatus(statusEl, "请填写用户名和密码", "error");
        return;
      }

      setStatus(statusEl, "注册中...", "loading");
      try {
        const res = await fetch(`${API_BASE}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username,
            password,
            nickname: nickname || null,
          }),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus(statusEl, `注册失败：${JSON.stringify(data)}`, "error");
          return;
        }
        setStatus(statusEl, `注册成功，用户名：${data.username}\n你现在可以直接去登录。`, "ok");
        const loginUsername = byId("loginUsername");
        if (loginUsername) loginUsername.value = username;
        const regPassword = byId("regPassword");
        if (regPassword) regPassword.value = "";
        switchTab("login");
      } catch (error) {
        setStatus(statusEl, `网络错误：${String(error)}`, "error");
      }
    }

    async function login() {
      const username = (byId("loginUsername")?.value || "").trim();
      const password = byId("loginPassword")?.value || "";
      const statusEl = byId("loginStatus");

      if (!username || !password) {
        setStatus(statusEl, "请输入用户名和密码", "error");
        return;
      }

      setStatus(statusEl, "登录中...", "loading");
      try {
        const res = await fetch(`${API_BASE}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok) {
          setStatus(statusEl, `登录失败：${JSON.stringify(data)}`, "error");
          return;
        }
        saveUserSession(data);
        setStatus(statusEl, `登录成功：${data.username}`, "ok");
        const loginPassword = byId("loginPassword");
        if (loginPassword) loginPassword.value = "";
      } catch (error) {
        setStatus(statusEl, `网络错误：${String(error)}`, "error");
      }
    }

    async function getMe() {
      const token = localStorage.getItem("gw_user_token") || "";
      const statusEl = byId("loginStatus");

      if (!token) {
        setStatus(statusEl, "当前没有本地 access token，请先登录", "error");
        updateSessionPanel({
          username: "未登录",
          state: "未校验",
          summary: "当前设备没有检测到有效会话。",
        });
        return;
      }

      setStatus(statusEl, "正在获取当前用户...", "loading");
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await res.json();
        if (!res.ok) {
          if (res.status === 401) clearUserSession();
          setStatus(statusEl, `获取失败：${JSON.stringify(data)}`, "error");
          updateSessionPanel({
            username: localStorage.getItem("gw_user_name") || "未知用户",
            state: "会话失效",
            summary: "会话可能已过期，请重新登录。",
          });
          return;
        }

        const expireAt = Number(localStorage.getItem("gw_access_expire_at") || 0);
        const expireIn = Number(localStorage.getItem("gw_access_expire_in") || 0);
        const now = Date.now();
        localStorage.setItem("gw_user_name", data.username || "");
        localStorage.setItem("gw_user_id", data.user_id || "");

        setStatus(statusEl, `当前用户：${data.username}（${data.status}）`, "ok");
        updateSessionPanel({
          username: data.username || "未知用户",
          state: data.status === "active" ? "正常" : data.status || "未知",
          expireAt,
          expireIn,
          checkedAt: now,
          summary: `账户校验通过，用户标识：${maskUserId(data.user_id)}`,
        });
      } catch (error) {
        setStatus(statusEl, `网络错误：${String(error)}`, "error");
        updateSessionPanel({
          username: localStorage.getItem("gw_user_name") || "未知用户",
          state: "网络异常",
          summary: "网络异常，暂时无法刷新账户状态。",
        });
      }
    }

    async function logout() {
      const statusEl = byId("loginStatus");
      setStatus(statusEl, "正在退出...", "loading");
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        clearUserSession();
        setStatus(statusEl, "已退出登录", "ok");
      } catch (error) {
        clearUserSession();
        setStatus(statusEl, `网络异常，已清理本地会话：${String(error)}`, "error");
      }
    }

    function onRegisterEnter(event) {
      if (event.key === "Enter") register();
    }

    function onLoginEnter(event) {
      if (event.key === "Enter") login();
    }

    const btnToLogin = byId("btnToLogin");
    const btnRegister = byId("btnRegister");
    const btnLogin = byId("btnLogin");
    const btnMe = byId("btnMe");
    const btnLogout = byId("btnLogout");

    const onTabRegisterClick = () => switchTab("register");
    const onTabLoginClick = () => switchTab("login");
    const onToLoginClick = () => switchTab("login");

    tabRegister.addEventListener("click", onTabRegisterClick);
    tabLogin.addEventListener("click", onTabLoginClick);
    btnToLogin?.addEventListener("click", onToLoginClick);
    btnRegister?.addEventListener("click", register);
    btnLogin?.addEventListener("click", login);
    btnMe?.addEventListener("click", getMe);
    btnLogout?.addEventListener("click", logout);

    handlers.push(() => tabRegister.removeEventListener("click", onTabRegisterClick));
    handlers.push(() => tabLogin.removeEventListener("click", onTabLoginClick));
    handlers.push(() => btnToLogin?.removeEventListener("click", onToLoginClick));
    handlers.push(() => btnRegister?.removeEventListener("click", register));
    handlers.push(() => btnLogin?.removeEventListener("click", login));
    handlers.push(() => btnMe?.removeEventListener("click", getMe));
    handlers.push(() => btnLogout?.removeEventListener("click", logout));

    ["regUsername", "regPassword", "regNickname"].forEach((id) => {
      const input = byId(id);
      if (!input) return;
      input.addEventListener("keydown", onRegisterEnter);
      handlers.push(() => input.removeEventListener("keydown", onRegisterEnter));
    });

    ["loginUsername", "loginPassword"].forEach((id) => {
      const input = byId(id);
      if (!input) return;
      input.addEventListener("keydown", onLoginEnter);
      handlers.push(() => input.removeEventListener("keydown", onLoginEnter));
    });

    const savedName = localStorage.getItem("gw_user_name");
    if (savedName) {
      updateSessionPanel({
        username: savedName,
        state: "待校验",
        expireAt: Number(localStorage.getItem("gw_access_expire_at") || 0),
        expireIn: Number(localStorage.getItem("gw_access_expire_in") || 0),
        summary: "检测到本地会话，建议刷新登录状态确认可用性。",
      });
      setStatus(byId("loginStatus"), `检测到本地会话：${savedName}`, "ok");
    }

    return () => {
      handlers.forEach((off) => off());
    };
  }

  function cleanupPage() {
    if (typeof cleanupCurrentPage === "function") {
      cleanupCurrentPage();
      cleanupCurrentPage = null;
    }
  }

  function runPageScripts() {
    ensureBrandElements();
    cleanupPage();
    const path = window.location.pathname.replace(/\/+$/, "") || "/";
    if (path === "/query") {
      cleanupCurrentPage = initQueryPage();
    } else if (path === "/register") {
      cleanupCurrentPage = initRegisterPage();
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", runPageScripts, { once: true });
  } else {
    runPageScripts();
  }

  ["swup:willReplaceContent", "swup:contentReplaced", "swup:content:replace"].forEach((eventName) => {
    document.addEventListener(eventName, cleanupPage);
  });
  ["swup:pageView", "swup:page:view"].forEach((eventName) => {
    document.addEventListener(eventName, runPageScripts);
  });

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) window.location.reload();
  });
})();
