const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Mapeo de secciones de marca a labels humanos en español ──────────
export const SECTION_LABELS: Record<string, string> = {
  TONE: "Tono de voz",
  AUDIENCE: "Audiencia",
  FORBIDDEN: "Palabras prohibidas",
  VISUAL: "Reglas visuales",
  MESSAGING: "Mensajes clave",
};

export function humanSection(section: string): string {
  return SECTION_LABELS[section] || section;
}

// ── Mapeo de errores HTTP a mensajes humanos ─────────────────────────
function humanizeError(status: number, body: string): string {
  // Intenta extraer detail del JSON si viene del backend
  let detail = body;
  try {
    const parsed = JSON.parse(body);
    if (parsed?.detail) {
      detail = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
    }
  } catch {
    /* ignore non-JSON bodies */
  }

  const lower = (detail || "").toLowerCase();

  // Errores específicos por contenido
  if (lower.includes("exceeds") && lower.includes("mb")) {
    return "La imagen supera el límite de 5 MB. Comprimir con Squoosh y vuelve a intentar.";
  }
  if (lower.includes("unsupported image type")) {
    return "Formato de imagen no soportado. Usa JPG, PNG o WebP.";
  }
  if (lower.includes("empty image")) {
    return "El archivo de imagen parece estar vacío. Vuelve a seleccionarlo.";
  }
  if (lower.includes("invalid email or password")) {
    return "Correo o contraseña incorrectos.";
  }
  if (lower.includes("missing bearer token") || lower.includes("invalid or expired token")) {
    return "Tu sesión expiró. Vuelve a iniciar sesión.";
  }
  if (lower.includes("not in allowed roles")) {
    return "No tienes permisos para esta acción.";
  }
  if (lower.includes("brand_not_found") || lower.includes("brand manual")) {
    return "No se encontró la marca. Crea una marca primero.";
  }
  if (lower.includes("no_brand_context") || lower.includes("similarity threshold")) {
    return "El sistema no encontró suficiente contexto de marca para tu pedido. Intenta una solicitud más alineada con la marca, o ajusta el manual.";
  }

  // Errores genéricos por código HTTP
  switch (status) {
    case 400:
      return detail || "La solicitud tiene datos inválidos.";
    case 401:
      return "No estás autenticado. Inicia sesión.";
    case 403:
      return "No tienes permisos para esta acción.";
    case 404:
      return "No encontramos lo que buscas.";
    case 409:
      return detail || "Esta acción no se puede ejecutar en el estado actual del item.";
    case 413:
      return "El archivo es demasiado grande.";
    case 415:
      return "Formato no soportado.";
    case 422:
      return "Datos del formulario inválidos. Revisa los campos.";
    case 429:
      return "Has alcanzado el límite del servicio gratuito. Espera unos minutos e inténtalo de nuevo.";
    case 500:
    case 502:
    case 503:
    case 504:
      return "Tuvimos un problema procesando tu solicitud. Intenta de nuevo en unos segundos.";
    default:
      return detail || `Error ${status}`;
  }
}

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
    throw new Error(humanizeError(res.status, text));
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
    if (!res.ok) {
      throw new Error(humanizeError(res.status, await res.text()));
    }
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
