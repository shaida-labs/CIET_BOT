import type { ChatMessage } from "./types";

type Session = { conversationId: string | null; messages: ChatMessage[] };
const key = "ciet-ai-session-v2";

export function loadSession(): Session {
  try {
    const value = window.localStorage.getItem(key);
    if (!value) return { conversationId: null, messages: [] };
    const parsed = JSON.parse(value) as Session;
    return {
      conversationId: parsed.conversationId ?? null,
      messages: Array.isArray(parsed.messages) ? parsed.messages.slice(-50) : [],
    };
  } catch {
    return { conversationId: null, messages: [] };
  }
}

export function saveSession(session: Session): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(session));
  } catch {
    // The widget remains usable when storage is unavailable or blocked.
  }
}

export function clearSession(): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore restricted storage environments.
  }
}
