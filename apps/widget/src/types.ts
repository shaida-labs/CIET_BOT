export type Language = "en" | "te" | "hi";

export type Citation = {
  document_id?: string;
  title: string;
  section?: string;
  url?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  confidence?: "verified" | "high" | "medium" | "low";
  citations?: Citation[];
  feedback?: "up" | "down";
};

export type ChatResponse = {
  conversation_id: string;
  message: ChatMessage;
  route: "faq" | "metric" | "rag" | "website" | "fallback";
};

export type WidgetConfig = {
  apiUrl: string;
  tenant: string;
  position: "bottom-left" | "bottom-right";
  primaryColor?: string;
  logoUrl?: string;
  privacyUrl?: string;
};
