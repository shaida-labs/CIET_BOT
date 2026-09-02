import React from "react";
import { createRoot } from "react-dom/client";
import { Widget } from "./Widget";
import { i18n } from "./i18n";
import "./fonts.css";
import "./widget.css";

const root = document.getElementById("ciet-ai-root");
// In Vite development, use the local proxy so the browser does not need a
// cross-origin request. Deployments keep an explicit VITE_API_URL (or the
// production default) for the standalone widget.
const apiUrl = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "" : "http://localhost:8000");
const snippet = document.getElementById("ciet-preview-snippet");
if (snippet) snippet.textContent = `<script src="/ciet-ai.js" data-api-url="${apiUrl}"></script>`;

if (!root) {
  throw new Error("CIET AI preview root was not found.");
}

try {
  createRoot(root).render(
    <React.StrictMode>
      <Widget
        config={{
          apiUrl,
          tenant: "ciet",
          position: "bottom-right",
        }}
      />
    </React.StrictMode>,
  );
} catch (error) {
  root.innerHTML = `
    <button class="ciet-preview-fallback" type="button">
      ${i18n.t("errors.previewMount")}
    </button>
  `;
  throw error;
}
