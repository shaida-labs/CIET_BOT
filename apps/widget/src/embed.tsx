import React from "react";
import { createRoot } from "react-dom/client";
import { Widget } from "./Widget";
import { i18n } from "./i18n";
import styles from "./widget.css?inline";
import notoTelugu400 from "@fontsource/noto-sans-telugu/files/noto-sans-telugu-telugu-400-normal.woff2?inline";
import notoTelugu700 from "@fontsource/noto-sans-telugu/files/noto-sans-telugu-telugu-700-normal.woff2?inline";
import notoDevanagari400 from "@fontsource/noto-sans-devanagari/files/noto-sans-devanagari-devanagari-400-normal.woff2?inline";
import notoDevanagari700 from "@fontsource/noto-sans-devanagari/files/noto-sans-devanagari-devanagari-700-normal.woff2?inline";
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
    apiUrl:
      external.apiUrl ??
      script?.dataset.apiUrl ??
      (import.meta.env.DEV ? "" : "http://localhost:8000"),
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

let fontsReady: Promise<void> | undefined;

function loadFont(family: string, source: string, weight: string): Promise<void> {
  const face = new FontFace(family, `url(${source})`, { style: "normal", weight });
  return face.load().then((loaded) => {
    document.fonts.add(loaded);
  });
}

function prepareFonts(): Promise<void> {
  fontsReady ??= Promise.all([
    loadFont("Noto Sans Telugu", notoTelugu400, "400"),
    loadFont("Noto Sans Telugu", notoTelugu700, "700"),
    loadFont("Noto Sans Devanagari", notoDevanagari400, "400"),
    loadFont("Noto Sans Devanagari", notoDevanagari700, "700"),
  ]).then(() => undefined);
  return fontsReady;
}

async function mount() {
  if (document.querySelector("ciet-ai-assistant")) return;
  await prepareFonts();
  const host = document.createElement("ciet-ai-assistant");
  host.setAttribute("role", "region");
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
  window.CIETAI = {
    open: () => window.dispatchEvent(new CustomEvent("ciet-ai:open")),
  };
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount, { once: true });
} else {
  mount();
}
