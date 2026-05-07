const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("cs_token");
}

function getRole(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("cs_role");
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user_id: string; email: string; role: string }>(
      "/api/v1/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) }
    ),
  demoUsers: () => request<{ users: Array<{ email: string; password: string; role: string }> }>(
    "/api/v1/auth/demo-users"
  ),
  health: () => request<{ status: string; mock_mode: Record<string, boolean> }>("/api/v1/health"),
  createBrand: (payload: any) =>
    request<any>("/api/v1/brand-dna", { method: "POST", body: JSON.stringify(payload) }),
  listBrands: () => request<any[]>("/api/v1/brands"),
  generate: (payload: any) =>
    request<any>("/api/v1/generate", { method: "POST", body: JSON.stringify(payload) }),
  listContent: (params?: { status?: string; brand_id?: string }) => {
    const q = new URLSearchParams();
    if (params?.status) q.set("status", params.status);
    if (params?.brand_id) q.set("brand_id", params.brand_id);
    const tail = q.toString() ? `?${q}` : "";
    return request<any[]>(`/api/v1/content${tail}`);
  },
  getContent: (id: string) => request<any>(`/api/v1/content/${id}`),
  decideText: (id: string, decision: "approved_text" | "rejected", notes?: string) =>
    request<any>(`/api/v1/audit/text/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ decision, notes }),
    }),
  auditImage: async (id: string, file: File) => {
    const token = getToken();
    const fd = new FormData();
    fd.append("image", file);
    const res = await fetch(`${API}/api/v1/audit/image/${id}`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) throw new Error(`${res.status} — ${await res.text()}`);
    return res.json();
  },
};

export const auth = {
  set(token: string, role: string, email: string) {
    if (typeof window === "undefined") return;
    window.localStorage.setItem("cs_token", token);
    window.localStorage.setItem("cs_role", role);
    window.localStorage.setItem("cs_email", email);
  },
  clear() {
    if (typeof window === "undefined") return;
    window.localStorage.removeItem("cs_token");
    window.localStorage.removeItem("cs_role");
    window.localStorage.removeItem("cs_email");
  },
  role: () => getRole(),
  token: () => getToken(),
  email: () => (typeof window === "undefined" ? null : window.localStorage.getItem("cs_email")),
};

export function landingPathForRole(role: string): string {
  if (role === "creator") return "/creator";
  if (role === "approver_a") return "/approver-a";
  if (role === "approver_b") return "/approver-b";
  return "/";
}
