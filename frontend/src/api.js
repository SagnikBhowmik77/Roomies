// Thin fetch wrapper: attaches the JWT, refreshes it once on 401, and
// surfaces the backend's typed error codes ({code, detail}).

const store = {
  get access() {
    return localStorage.getItem("access");
  },
  get refresh() {
    return localStorage.getItem("refresh");
  },
  set(tokens) {
    if (tokens.access) localStorage.setItem("access", tokens.access);
    if (tokens.refresh) localStorage.setItem("refresh", tokens.refresh);
  },
  clear() {
    localStorage.removeItem("access");
    localStorage.removeItem("refresh");
  },
};

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `Request failed (${status})`);
    this.status = status;
    this.code = body?.code || "error";
    this.body = body;
  }
}

async function rawRequest(path, { method = "GET", body, headers = {} } = {}) {
  const h = { ...headers };
  if (body !== undefined) h["Content-Type"] = "application/json";
  if (store.access) h["Authorization"] = `Bearer ${store.access}`;
  const res = await fetch(path, {
    method,
    headers: h,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return { res, data: null };
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  return { res, data };
}

async function tryRefresh() {
  if (!store.refresh) return false;
  const { res, data } = await rawRequest("/api/v1/auth/refresh/", {
    method: "POST",
    body: { refresh: store.refresh },
  });
  if (!res.ok) {
    store.clear();
    return false;
  }
  store.set(data);
  return true;
}

export async function api(path, options = {}) {
  let { res, data } = await rawRequest(path, options);
  if (res.status === 401 && store.refresh && !path.includes("/auth/")) {
    if (await tryRefresh()) ({ res, data } = await rawRequest(path, options));
  }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const tokens = store;
export const idempotencyKey = () => crypto.randomUUID();
