const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const tokenKey = "ciet-admin-token";

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

export function getToken() {
  return localStorage.getItem(tokenKey);
}

export function setToken(token: string) {
  localStorage.setItem(tokenKey, token);
}

export function logout() {
  localStorage.removeItem(tokenKey);
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: HeadersInit = init.body instanceof FormData ? {} : { "Content-Type": "application/json" };
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...headers,
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) throw new Error(await response.text());
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

export const client = {
  login: async (username: string, password: string) => api<{ access_token: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
  bootstrap: async (username: string, password: string) => api<{ access_token: string }>("/api/v1/auth/bootstrap", { method: "POST", body: JSON.stringify({ username, password }) }),
  analytics: async () => api<Analytics>("/api/v1/admin/analytics"),
  faqs: async () => api<FAQ[]>("/api/v1/admin/faqs"),
  createFaq: async (payload: Omit<FAQ, "id" | "updated_at">) => api<FAQ>("/api/v1/admin/faqs", { method: "POST", body: JSON.stringify(payload) }),
  metrics: async () => api<Metric[]>("/api/v1/admin/metrics"),
  createMetric: async (payload: Omit<Metric, "id" | "updated_at">) => api<Metric>("/api/v1/admin/metrics", { method: "POST", body: JSON.stringify(payload) }),
  documents: async () => api<Document[]>("/api/v1/admin/documents"),
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api<Document>("/api/v1/admin/documents", { method: "POST", body: form });
  },
  refreshKnowledge: async () => api<{ status: string; chunks: string }>("/api/v1/admin/knowledge/refresh", { method: "POST" }),
  conversations: async () => api<Record<string, unknown>[]>("/api/v1/admin/conversations"),
};
