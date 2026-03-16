function $(id) {
  return document.getElementById(id);
}

const storage = {
  get(key, fallback = "") {
    try {
      return localStorage.getItem(key) || fallback;
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // ignore
    }
  },
};

function pretty(value) {
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

async function request(path, options = {}) {
  const apiBase = $("apiBase").value.trim();
  const adminToken = $("adminToken").value.trim();

  storage.set("console_api_base", apiBase);
  storage.set("console_admin_token", adminToken);

  const headers = {
    ...(options.headers || {}),
  };
  if (adminToken) {
    headers["X-Admin-Token"] = adminToken;
  }
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${apiBase}${path}`, {
    ...options,
    headers,
  });
  const contentType = res.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await res.json() : await res.text();
  return { ok: res.ok, status: res.status, data };
}

function fillDefaults() {
  $("apiBase").value = storage.get("console_api_base", `${window.location.origin}/api/v1`);
  $("adminToken").value = storage.get("console_admin_token", "");
}

function bindHealth() {
  $("btnHealth").addEventListener("click", async () => {
    $("healthOutput").textContent = "请求中...";
    try {
      const result = await request("/health");
      $("healthOutput").textContent = pretty(result);
    } catch (error) {
      $("healthOutput").textContent = pretty(error);
    }
  });
}

function bindSearch() {
  $("btnSearch").addEventListener("click", async () => {
    $("searchOutput").textContent = "查询中...";
    const searchType = $("searchType").value;
    const endpoint = searchType === "adjustments" ? "/search/adjustments" : "/search/announcements";
    const payload = {
      school_name: $("schoolName").value.trim() || null,
      keywords: $("keywords").value.trim() || null,
      page: 1,
      page_size: Number($("pageSize").value || 20),
      refresh: $("refresh").checked,
    };
    if (searchType === "adjustments") {
      payload.major = $("major").value.trim() || null;
      payload.region = $("region").value.trim() || null;
    }
    try {
      const result = await request(endpoint, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      $("searchOutput").textContent = pretty(result);
    } catch (error) {
      $("searchOutput").textContent = pretty(error);
    }
  });
}

function bindIngest() {
  $("btnIngest").addEventListener("click", async () => {
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
    try {
      const result = await request("/content", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      $("ingestOutput").textContent = pretty(result);
    } catch (error) {
      $("ingestOutput").textContent = pretty(error);
    }
  });
}

function bindOffline() {
  $("btnOffline").addEventListener("click", async () => {
    $("offlineOutput").textContent = "提交中...";
    const payload = {
      action: "offline",
      content_id: $("offlineContentId").value.trim(),
      reason: $("offlineReason").value.trim() || "manual offline",
    };
    try {
      const result = await request("/admin/manual-entry", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      $("offlineOutput").textContent = pretty(result);
    } catch (error) {
      $("offlineOutput").textContent = pretty(error);
    }
  });
}

fillDefaults();
bindHealth();
bindSearch();
bindIngest();
bindOffline();
