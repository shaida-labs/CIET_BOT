// Same-origin on purpose: nginx forwards /api/ to the backend, so the bundle
// never bakes in a host. This keeps the admin usable from localhost, a LAN IP,
// or any deployed domain without rebuilding. Vite dev serves the same proxy.
const API_URL = "";

export type FAQ = { id: string; question: string; answer: string; language: string; source: string; is_active: boolean; updated_at: string };
export type Metric = { id: string; name: string; value: string; unit?: string; verified_by: string; source: string; is_sensitive_stat: boolean; updated_at: string };
export type Document = { id: string; title: string; source: string; file_path: string; mime_type: string; status: string; uploaded_at: string };
export type Analytics = {
  total_queries: number;
  failed_queries: number;
  avg_response_ms: number;
  website_usage: number;
  whatsapp_usage: number;
  user_satisfaction: number;
  popular_questions: { query: string; count: number }[];
  document_usage: { title: string; count: number }[];
};
export type Feedback = { id: string; message_id: string; rating: "up" | "down"; comment?: string; message_content: string; conversation_id: string; created_at: string };
export type AuthResponse = { authenticated: true; email?: string; role?: string; challenge?: string; otp_required?: boolean };

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function logout() {
  await fetch(`${API_URL}/api/v1/auth/logout`, { method: "POST", credentials: "include", headers: csrfHeaders() });
}

function csrfHeaders(): HeadersInit {
  const csrf = document.cookie.split("; ").find((item) => item.startsWith("ciet_csrf_token="))?.split("=")[1];
  return csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {};
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: HeadersInit = init.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      ...headers,
      ...(init.method && !["GET", "HEAD"].includes(init.method) ? csrfHeaders() : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    let detail = "The request could not be completed.";
    try {
      const body = await response.json() as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      detail = "The request could not be completed.";
    }
    throw new ApiError(response.status, detail);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const client = {
  login: async (email: string, password: string) => api<AuthResponse>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  verifyOtp: async (challenge: string, code: string) => api<AuthResponse>("/api/v1/auth/otp/verify", { method: "POST", body: JSON.stringify({ challenge, code }) }),
  resendOtp: async (challenge: string) => api<AuthResponse>("/api/v1/auth/otp/request", { method: "POST", body: JSON.stringify({ challenge }) }),
  inviteAdmin: async (payload: { name: string; email: string; role: string }) => api<{ message: string }>("/api/v1/auth/invitations", { method: "POST", body: JSON.stringify(payload) }),
  acceptInvitation: async (payload: { token: string; name: string; password: string }) => api<{ message: string }>("/api/v1/auth/accept-invitation", { method: "POST", body: JSON.stringify(payload) }),
  session: async () => api<{ authenticated: true; email: string; role: string }>("/api/v1/auth/session"),
  analytics: async () => api<Analytics>("/api/v1/admin/analytics"),
  faqs: async () => api<FAQ[]>("/api/v1/admin/faqs"),
  createFaq: async (payload: Omit<FAQ, "id" | "updated_at">) => api<FAQ>("/api/v1/admin/faqs", { method: "POST", body: JSON.stringify(payload) }),
  updateFaq: async (id: string, payload: Omit<FAQ, "id" | "updated_at">) => api<FAQ>(`/api/v1/admin/faqs/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  metrics: async () => api<Metric[]>("/api/v1/admin/metrics"),
  createMetric: async (payload: Omit<Metric, "id" | "updated_at">) => api<Metric>("/api/v1/admin/metrics", { method: "POST", body: JSON.stringify(payload) }),
  updateMetric: async (id: string, payload: Omit<Metric, "id" | "updated_at">) => api<Metric>(`/api/v1/admin/metrics/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  documents: async () => api<Document[]>("/api/v1/admin/documents"),
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Document>("/api/v1/admin/documents", { method: "POST", body: form });
  },
  refreshKnowledge: async () => api<{ status: string; documents: number }>("/api/v1/admin/knowledge/refresh", { method: "POST" }),
  conversations: async () => api<Record<string, unknown>[]>("/api/v1/admin/conversations"),
  feedback: async () => api<Feedback[]>("/api/v1/admin/feedback"),
  deleteDocument: async (id: string) => api<void>(`/api/v1/admin/documents/${id}`, { method: "DELETE" }),
  reprocessDocument: async (id: string) => api<{ id: string; status: string }>(`/api/v1/admin/documents/${id}/reprocess`, { method: "POST" }),
  deleteFaq: async (id: string) => api<void>(`/api/v1/admin/faqs/${id}`, { method: "DELETE" }),
  deleteMetric: async (id: string) => api<void>(`/api/v1/admin/metrics/${id}`, { method: "DELETE" }),
};
