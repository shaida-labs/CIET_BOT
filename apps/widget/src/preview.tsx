import React from "react";
import { createRoot } from "react-dom/client";
import { Widget } from "./Widget";
import { PreviewPage } from "./PreviewPage";
import { i18n } from "./i18n";
import "./fonts.css";
import "./widget.css";

const root = document.getElementById("ciet-ai-root");
// In Vite development, use the local proxy so the browser does not need a
// cross-origin request. Deployments keep an explicit VITE_API_URL (or the
// production default) for the standalone widget.
const apiUrl = import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? "" : "http://localhost:8000");

if (!root) {
  throw new Error("CIET AI preview root was not found.");
}

// Add body class for preview page styling
document.body.classList.add("ciet-preview-page");

try {
  createRoot(root).render(
    <React.StrictMode>
      <PreviewPage>
        <Widget
          config={{
            apiUrl,
            tenant: "ciet",
            position: "bottom-right",
          }}
        />
      </PreviewPage>
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
