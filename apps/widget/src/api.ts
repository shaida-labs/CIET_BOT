import type { ChatResponse, Language, WidgetConfig } from "./types";

const timeout = 30_000;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  config: WidgetConfig,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`${config.apiUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      signal: controller.signal,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        "X-CIET-Tenant": config.tenant,
        ...init.headers,
      },
    });
    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string };
        detail = body.detail ?? detail;
      } catch {
        // Preserve the status when the server did not return JSON.
      }
      throw new ApiError(detail, response.status);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("The request timed out. Please try again.", 408);
    }
    if (error instanceof TypeError) {
      throw new ApiError("The CIET AI service could not be reached.", 0);
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function sendMessage(
  config: WidgetConfig,
  message: string,
  language: Language,
  conversationId: string | null,
): Promise<ChatResponse> {
  return request<ChatResponse>(config, "/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      language,
      channel: "website",
      conversation_id: conversationId,
    }),
  });
}

export async function sendFeedback(
  config: WidgetConfig,
  messageId: string,
  rating: "up" | "down",
): Promise<void> {
  await request(config, "/api/v1/feedback", {
    method: "POST",
    body: JSON.stringify({ message_id: messageId, rating }),
  });
}
