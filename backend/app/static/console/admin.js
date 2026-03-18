function $(id) {
  return document.getElementById(id);
}

const API_BASE = "/api/v1";
const MODERN_ADMIN_URL = "/admin/";

function text(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function pretty(value) {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  return { ok: response.ok, status: response.status, data };
}

function goToModernAdmin() {
  window.location.replace(MODERN_ADMIN_URL);
}

function setLoginView(loggedIn) {
  $("loginCard").classList.toggle("hidden", loggedIn);
  $("panelCard").classList.toggle("hidden", !loggedIn);
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-tab") === name);
  });
  document.querySelectorAll(".tab-panel").forEach((el) => {
    el.classList.toggle("active", el.id === `tab-${name}`);
  });
}

async function checkSession() {
  const result = await api("/admin/auth/me");
  if (!result.ok) {
    setLoginView(false);
    $("loginStatus").textContent = "旧控制台已停用，正在跳转到新版后台...";
    setTimeout(goToModernAdmin, 300);
    return;
  }
  goToModernAdmin();
}

async function doLogin() {
  $("loginStatus").textContent = "旧控制台已停用，正在跳转到新版后台...";
  goToModernAdmin();
}

async function doLogout() {
  goToModernAdmin();
}

function renderUsers(items) {
  const tbody = $("usersTbody");
  if (!items.length) {
    tbody.innerHTML = "<tr><td colspan='7' class='muted'>暂无用户数据</td></tr>";
    return;
  }
  tbody.innerHTML = items
    .map(
      (item) => `<tr data-user-id="${text(item.id)}">
      <td>${text(item.id)}</td>
      <td>${text(item.username)}</td>
      <td>${text(item.nickname || "-")}</td>
      <td>
        <select class="mini-select" data-role="state">
          <option value="active" ${item.status === "active" ? "selected" : ""}>active</option>
          <option value="blocked" ${item.status === "blocked" ? "selected" : ""}>blocked</option>
        </select>
      </td>
      <td>${item.is_admin ? "是" : "否"}</td>
      <td>${text(item.last_login_at || "-")}</td>
      <td>
        <button class="mini-btn" data-role="save">保存</button>
        <button class="mini-btn" data-role="promote">提升管理员</button>
      </td>
    </tr>`,
    )
    .join("");
}

async function loadUsers() {
  $("usersStatus").textContent = "正在加载用户...";
  const keyword = $("keyword").value.trim();
  const state = $("stateFilter").value;
  const query = new URLSearchParams({ page: "1", page_size: "50" });
  if (keyword) query.set("keyword", keyword);
  if (state) query.set("state", state);
  const result = await api(`/admin/users?${query.toString()}`);
  if (!result.ok) {
    $("usersStatus").textContent = `加载失败（${result.status}）：${pretty(result.data)}`;
    return;
  }
  const items = result.data.items || [];
  renderUsers(items);
  $("usersStatus").textContent = `共 ${result.data.total} 个用户`;
}

async function saveUserState(row) {
  const userId = row.getAttribute("data-user-id");
  const nextState = row.querySelector('[data-role="state"]').value;
  const result = await api(`/admin/users/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    body: JSON.stringify({ status: nextState }),
  });
  if (!result.ok) {
    $("usersStatus").textContent = `保存失败（${result.status}）：${pretty(result.data)}`;
    return;
  }
  $("usersStatus").textContent = `用户 ${userId} 状态已更新为 ${nextState}`;
}

async function promoteUser(row) {
  const userId = row.getAttribute("data-user-id");
  const result = await api(`/admin/users/${encodeURIComponent(userId)}/promote`, {
    method: "POST",
  });
  if (!result.ok) {
    $("usersStatus").textContent = `提升失败（${result.status}）：${pretty(result.data)}`;
    return;
  }
  $("usersStatus").textContent = `用户 ${userId} 已提升为管理员`;
  await loadUsers();
}

async function doIngest() {
  $("ingestOutput").textContent = "提交中...";
  const payload = {
    category: $("ingestCategory").value,
    title: $("ingestTitle").value.trim(),
    body: $("ingestBody").value.trim(),
    summary: $("ingestSummary").value.trim() || null,
    school_name: $("ingestSchool").value.trim() || null,
    source_url: $("ingestSourceUrl").value.trim() || null,
    source_type: $("ingestSourceType").value,
    major: $("ingestMajor").value.trim() || null,
    region: $("ingestRegion").value.trim() || null,
  };
  const result = await api("/content", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  $("ingestOutput").textContent = pretty(result);
}

async function doOffline() {
  $("offlineOutput").textContent = "提交中...";
  const payload = {
    action: "offline",
    content_id: $("offlineContentId").value.trim(),
    reason: $("offlineReason").value.trim() || "manual offline",
  };
  const result = await api("/admin/manual-entry", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  $("offlineOutput").textContent = pretty(result);
}

async function loadHealth() {
  $("healthOutput").textContent = "请求中...";
  const result = await api("/health");
  $("healthOutput").textContent = pretty(result);
}

async function doChangePassword() {
  const oldPassword = $("oldPassword").value;
  const newPassword = $("newPassword").value;
  if (!oldPassword || !newPassword) {
    $("passwordOutput").textContent = "请输入旧密码和新密码";
    return;
  }
  $("passwordOutput").textContent = "提交中...";
  const result = await api("/admin/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
  $("passwordOutput").textContent = pretty(result);
  if (result.ok) {
    $("oldPassword").value = "";
    $("newPassword").value = "";
  }
}

async function loadAudits() {
  $("auditOutput").textContent = "加载中...";
  const result = await api("/admin/audits?page=1&page_size=30");
  $("auditOutput").textContent = pretty(result);
}

function bindEvents() {
  $("btnLogin").addEventListener("click", doLogin);
  $("btnLogout").addEventListener("click", doLogout);
  $("btnRefreshUsers").addEventListener("click", loadUsers);
  $("btnIngest").addEventListener("click", doIngest);
  $("btnOffline").addEventListener("click", doOffline);
  $("btnHealth").addEventListener("click", loadHealth);
  $("btnChangePassword").addEventListener("click", doChangePassword);
  $("btnAudit").addEventListener("click", loadAudits);

  $("keyword").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      loadUsers();
    }
  });
  $("stateFilter").addEventListener("change", loadUsers);

  $("usersTbody").addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    const row = target.closest("tr");
    if (!row) return;
    const role = target.getAttribute("data-role");
    if (role === "save") {
      void saveUserState(row);
    } else if (role === "promote") {
      void promoteUser(row);
    }
  });

  document.querySelectorAll(".tab").forEach((el) => {
    el.addEventListener("click", () => {
      const tab = el.getAttribute("data-tab");
      if (tab) activateTab(tab);
    });
  });
}

bindEvents();
activateTab("users");
void checkSession();
