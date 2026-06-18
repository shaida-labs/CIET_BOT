import type { ChatMessage, ChatResponse, Language, WidgetConfig } from "./types";

const timeout = 30_000;

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
      headers: {
        "Content-Type": "application/json",
        "X-CIET-Tenant": config.tenant,
        ...init.headers,
      },
    });
    if (!response.ok) {
      throw new Error(`Request failed with status ${response.status}`);
    }
    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function sendMessage(
  config: WidgetConfig,
  message: string,
  language: Language,
  conversationId: string | null,
  history: ChatMessage[],
): Promise<ChatResponse> {
  return request<ChatResponse>(config, "/api/v1/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      language,
      channel: "website",
      conversation_id: conversationId,
      history: history.slice(-10).map(({ role, content }) => ({ role, content })),
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
