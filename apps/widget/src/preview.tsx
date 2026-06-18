import React from "react";
import { createRoot } from "react-dom/client";
import { Widget } from "./Widget";
import { i18n } from "./i18n";
import "./widget.css";

const root = document.getElementById("ciet-ai-root");

if (!root) {
  throw new Error("CIET AI preview root was not found.");
}

try {
  createRoot(root).render(
    <React.StrictMode>
      <Widget
        config={{
          apiUrl: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
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
