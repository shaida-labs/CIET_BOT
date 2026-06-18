import React from "react";
import { createRoot } from "react-dom/client";
import { Widget } from "./Widget";
import { i18n } from "./i18n";
import styles from "./widget.css?inline";
import type { WidgetConfig } from "./types";

declare global {
  interface Window {
    CIET_AI_CONFIG?: Partial<WidgetConfig>;
    CIETAI?: { open: () => void };
  }
}

function configFromScript(): WidgetConfig {
  const script = document.currentScript as HTMLScriptElement | null;
  const external = window.CIET_AI_CONFIG ?? {};
  return {
    apiUrl: external.apiUrl ?? script?.dataset.apiUrl ?? "http://localhost:8000",
    tenant: external.tenant ?? script?.dataset.tenant ?? "ciet",
    position:
      external.position ??
      (script?.dataset.position as WidgetConfig["position"]) ??
      "bottom-right",
    primaryColor: external.primaryColor ?? script?.dataset.primaryColor,
    logoUrl: external.logoUrl ?? script?.dataset.logoUrl,
    privacyUrl: external.privacyUrl ?? script?.dataset.privacyUrl,
  };
}

function mount() {
  if (document.querySelector("ciet-ai-assistant")) return;
  const host = document.createElement("ciet-ai-assistant");
  host.setAttribute("aria-label", i18n.t("header.dialog"));
  const shadow = host.attachShadow({ mode: "open" });
  const style = document.createElement("style");
  style.textContent = styles;
  const root = document.createElement("div");
  shadow.append(style, root);
  document.body.appendChild(host);
  createRoot(root).render(
    <React.StrictMode>
      <Widget config={configFromScript()} />
    </React.StrictMode>,
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount, { once: true });
} else {
  mount();
}
