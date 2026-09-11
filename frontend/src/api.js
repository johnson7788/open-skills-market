const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const TOKEN_KEY = "skill-market:token";

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

function authHeaders(extra = {}) {
  const token = getToken();
  const headers = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: authHeaders(options.headers || {}),
  });
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    const err = new Error(detail);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

export function fetchSkills(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.search) searchParams.set("search", params.search);
  if (params.tab && params.tab !== "all") searchParams.set("tab", params.tab);
  if (params.category) searchParams.set("category", params.category);
  const query = searchParams.toString();
  return request(`/api/skills${query ? `?${query}` : ""}`);
}

export function fetchSkill(slug) {
  return request(`/api/skills/${encodeURIComponent(slug)}`);
}

export function fetchCategories() {
  return request(`/api/categories`);
}

// ── 鉴权 ──
export async function loginApi(username) {
  const response = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username }),
  });
  if (!response.ok) {
    let detail = `登录失败：${response.status}`;
    try {
      const body = await response.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return response.json();
}

export function fetchMe() {
  return request(`/api/auth/me`);
}

export function logoutApi() {
  return fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    headers: authHeaders(),
  }).catch(() => {});
}

/**
 * 流式对话（SSE）。onEvent(event, data) 在每个事件到达时回调。
 * 事件：text / tool / done / error。
 */
export async function streamChat({ slug, messages, conversationId, onEvent, signal }) {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ slug, conversation_id: conversationId || undefined, messages }),
    signal,
  });

  if (!response.ok || !response.body) {
    const text = await response.text().catch(() => "");
    throw new Error(`Chat 请求失败：${response.status} ${text}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);

      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data = line.slice(5).trim();
      }
      if (!data) continue;

      let parsed;
      try {
        parsed = JSON.parse(data);
      } catch {
        parsed = { raw: data };
      }
      onEvent?.(event, parsed);
    }
  }
}

export function stopChat(slug, conversationId) {
  return fetch(
    `${API_BASE}/api/chat/stop?slug=${encodeURIComponent(slug || "")}&conversation_id=${encodeURIComponent(conversationId || "")}`,
    { method: "POST", headers: authHeaders() }
  ).catch(() => {});
}

export function fetchChatHistory(slug, conversationId) {
  return request(
    `/api/chat/history?slug=${encodeURIComponent(slug)}&conversation_id=${encodeURIComponent(conversationId || "")}`
  );
}

export function fetchConversations(slug) {
  const q = slug ? `?slug=${encodeURIComponent(slug)}` : "";
  return request(`/api/chat/conversations${q}`);
}

export function fetchArtifacts(slug, conversationId) {
  return request(
    `/api/chat/artifacts?slug=${encodeURIComponent(slug)}&conversation_id=${encodeURIComponent(conversationId || "")}`
  );
}

export function artifactUrl(slug, path, conversationId) {
  const token = getToken();
  return (
    `${API_BASE}/api/chat/artifact?slug=${encodeURIComponent(slug)}` +
    `&path=${encodeURIComponent(path)}` +
    `&conversation_id=${encodeURIComponent(conversationId || "")}` +
    (token ? `&token=${encodeURIComponent(token)}` : "")
  );
}
