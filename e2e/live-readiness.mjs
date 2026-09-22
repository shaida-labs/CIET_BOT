import { execSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { AxePuppeteer } from "@axe-core/puppeteer";
import puppeteer from "puppeteer";

const WEB_URL = process.env.CIET_E2E_WEB_URL || "http://localhost:8080";
const API_URL = process.env.CIET_E2E_API_URL || "http://localhost:8000";
const EMAIL = process.env.CIET_E2E_ADMIN_EMAIL || "ciet-e2e@local.invalid";
const PASSWORD = process.env.CIET_E2E_ADMIN_PASSWORD || "CIET-e2e-password-2026!";
const evidenceDir = path.resolve("qa_evidence/screenshots/live");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function waitFor(url) {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch { /* service is starting */ }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function clickText(page, text) {
  const clicked = await page.evaluate((label) => {
    const button = [...document.querySelectorAll("button")].find((item) => item.textContent?.includes(label));
    button?.click();
    return Boolean(button);
  }, text);
  assert(clicked, `Button not found: ${text}`);
}

async function setInput(page, selector, value) {
  await page.$eval(selector, (element, nextValue) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(element, nextValue);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }, value);
}

async function adminApi(page, route, init = {}) {
  return page.evaluate(async ({ apiUrl, route, init }) => {
    const csrf = document.cookie.split("; ").find((item) => item.startsWith("ciet_csrf_token="))?.split("=")[1];
    const response = await fetch(`${apiUrl}${route}`, {
      ...init,
      credentials: "include",
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(init.method && !["GET", "HEAD"].includes(init.method) && csrf ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
      },
    });
    const body = response.status === 204 ? null : await response.json().catch(() => null);
    return { ok: response.ok, status: response.status, body };
  }, { apiUrl: API_URL, route, init });
}

async function chatFromWidget(page, message, language = "en") {
  return page.evaluate(async ({ apiUrl, message, language }) => {
    const response = await fetch(`${apiUrl}/api/v1/chat`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CIET-Tenant": "ciet" },
      body: JSON.stringify({ message, language, channel: "website", history: [] }),
    });
    return { status: response.status, body: await response.json() };
  }, { apiUrl: API_URL, message, language });
}

async function poll(check, description, attempts = 60) {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const value = await check();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`Timed out waiting for ${description}`);
}

async function readLocalOutbox(email) {
  const digest = createHash("sha256").update(email).digest("hex");
  const hostPath = path.resolve("services/api/storage/mail-outbox", `${digest}.eml`);
  try {
    return await readFile(hostPath, "utf8");
  } catch { /* fall through to the container volume */ }
  try {
    return execSync(`docker compose exec -T api cat /app/storage/mail-outbox/${digest}.eml`, {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
  } catch {
    return null;
  }
}

async function waitForFreshOtp(email, before) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    const current = await readLocalOutbox(email);
    if (current && current !== before) {
      const match = current.match(/verification code is (\d{6})/);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(
    "The OTP email was not delivered to the local mail outbox. Real SMTP is configured, so the "
    + "test address never receives a readable code. Re-run the stack with the E2E overlay so the "
    + "OTP email lands in the local outbox: "
    + "docker compose -f docker-compose.yml -f docker-compose.e2e.yml up -d",
  );
}

function assertNoSeriousAxeViolations(result, surface) {
  const blocking = result.violations.filter((item) => ["serious", "critical"].includes(item.impact));
  assert(
    blocking.length === 0,
    `${surface} has serious/critical axe violations: ${blocking.map((item) => `${item.id} (${item.nodes.map((node) => `${node.target.join(" > ")}: ${node.failureSummary}`).join(" | ")})`).join(", ")}`,
  );
  return result.violations.map((item) => ({
    id: item.id,
    impact: item.impact,
    nodes: item.nodes.length,
    targets: item.nodes.map((node) => node.target.join(" > ")),
  }));
}

await mkdir(evidenceDir, { recursive: true });
await Promise.all([waitFor(`${WEB_URL}/healthz`), waitFor(`${API_URL}/readyz`)]);

const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
  // Bound CDP calls so a stuck capture surfaces as a failure instead of hanging.
  protocolTimeout: 60000,
});

// Real-browser hygiene:
//  - failures  -> uncaught page errors, failed requests, HTTP 5xx, console
//                 errors that are not explained by an observed 4xx response;
//  - warnings  -> HTTP 4xx responses (for example the expected unauthenticated
//                 probe during boot) and the console noise they produce.
const browserIssues = { admin: { failures: [], warnings: [] }, widget: { failures: [], warnings: [] } };

function watchPage(page, name) {
  const observedClientErrors = new Set();
  page.on("response", (response) => {
    const status = response.status();
    if (status >= 500) browserIssues[name].failures.push(`http ${status}: ${response.url()}`);
    else if (status >= 400) {
      observedClientErrors.add(response.url());
      browserIssues[name].warnings.push(`http ${status}: ${response.url()}`);
    }
  });
  page.on("console", (message) => {
    const type = typeof message.type === "function" ? message.type() : message.type;
    if (type !== "error") return;
    const location = typeof message.location === "function" ? message.location() : {};
    const text = `console.error: ${message.text().slice(0, 200)} (${location.url || "no-url"})`;
    const explained = location.url && observedClientErrors.has(location.url);
    if (explained) browserIssues[name].warnings.push(text);
    else browserIssues[name].failures.push(text);
  });
  page.on("pageerror", (error) => browserIssues[name].failures.push(`pageerror: ${String(error).slice(0, 300)}`));
  page.on("requestfailed", (request) => {
    const reason = request.failure()?.errorText || "unknown";
    // Chrome cancels in-flight requests during navigation; those are not defects.
    if (reason.includes("ERR_ABORTED")) return;
    browserIssues[name].failures.push(`requestfailed: ${reason} ${request.url()}`);
  });
}

// Evidence capture must not be able to fail the run on its own. Chrome refuses
// full-page captures beyond ~16k CSS pixels (the admin logs view is a bounded
// 200-row table that exceeds that at 375px), so measure first and fall back to
// a viewport capture, reporting the reason.
async function safeScreenshot(page, file, label, { fullPage = true } = {}) {
  // A bounded per-attempt timeout keeps a slow capture from consuming the whole
  // run: the retry below usually succeeds immediately.
  const attempt = (options) => page.screenshot({ path: file, timeout: 20000, ...options });
  const metrics = await page
    .evaluate(() => ({
      width: document.documentElement.scrollWidth,
      height: document.documentElement.scrollHeight,
    }))
    .catch(() => null);
  if (fullPage && metrics && metrics.height > 16000) {
    console.warn(`screenshot_viewport_only ${label}: page height ${metrics.height}px exceeds the full-page capture limit`);
    await attempt({ fullPage: false });
    return;
  }
  try {
    await attempt({ fullPage });
  } catch (error) {
    console.warn(`screenshot_retry ${label}: ${error.message} metrics=${JSON.stringify(metrics)}`);
    await attempt({ fullPage: false });
  }
}

let admin;
let widget;
let faqId;
let documentId;
let placementBackups = [];
let ingestionMode = "not-run";
try {
  admin = await browser.newPage();
  watchPage(admin, "admin");
  await admin.setViewport({ width: 1440, height: 1000 });
  await admin.goto(`${WEB_URL}/admin/`, { waitUntil: "networkidle2" });
  const outboxBefore = await readLocalOutbox(EMAIL);
  await setInput(admin, 'input[type="email"]', EMAIL);
  await setInput(admin, 'input[type="password"]', PASSWORD);
  await admin.click('button[type="submit"]');
  await admin.waitForFunction(
    () => document.querySelector("#admin-otp") || document.querySelector(".error"),
    { timeout: 15000 },
  );
  if (!(await admin.$("#admin-otp"))) {
    const loginError = await admin.evaluate(() => document.querySelector(".error")?.textContent || "unknown login error");
    throw new Error(
      `Admin login failed before OTP (${loginError}). `
      + "Provision the local E2E administrator with: docker compose exec api python -m scripts.local_e2e_admin create",
    );
  }
  const otp = await waitForFreshOtp(EMAIL, outboxBefore);
  await setInput(admin, "#admin-otp", otp);
  await admin.click('button[type="submit"]');
  await admin.waitForSelector(".shell", { timeout: 15000 });
  await safeScreenshot(admin, path.join(evidenceDir, "admin-1440.png"), "admin-1440");

  const initialMetrics = await adminApi(admin, "/api/v1/admin/metrics");
  assert(initialMetrics.ok, "Could not list live metrics");
  placementBackups = initialMetrics.body.filter((metric) => metric.name.trim().toLowerCase() === "placement percentage");
  for (const metric of placementBackups) {
    const removed = await adminApi(admin, `/api/v1/admin/metrics/${metric.id}`, { method: "DELETE" });
    assert(removed.ok, "Could not establish the no-placement-metric state");
  }

  widget = await browser.newPage();
  watchPage(widget, "widget");
  await widget.setViewport({ width: 1440, height: 1000 });
  await widget.goto(`${WEB_URL}/widget/embed-test.html`, { waitUntil: "networkidle2" });
  await widget.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector("button"));
  const shadowMounted = await widget.evaluate(() => Boolean(document.querySelector("ciet-ai-assistant")?.shadowRoot));
  assert(shadowMounted, "Production widget did not mount in Shadow DOM");

  const missing = await chatFromWidget(widget, "What is the placement percentage?");
  assert(missing.status === 200, `Placement fallback returned ${missing.status}`);
  assert(missing.body.message.confidence === "low", "Missing placement metric did not fail closed");
  assert(!missing.body.message.content.includes("0%"), "Missing placement metric returned 0%");

  await clickText(admin, "Metrics");
  await admin.waitForSelector('input[aria-label="Metric name"]');
  await admin.type('input[aria-label="Metric name"]', "placement percentage");
  await admin.type('input[aria-label="Verified metric value"]', "92%");
  await admin.type('input[aria-label="Verified by"]', "Placement Office");
  await admin.type('input[aria-label="Metric source"]', "Official Placement Report");
  await clickText(admin, "Add Metric");

  const createdMetric = await poll(async () => {
    const response = await adminApi(admin, "/api/v1/admin/metrics");
    return response.body?.find((metric) => metric.name === "placement percentage" && metric.value === "92%");
  }, "created placement metric");
  const verified = await chatFromWidget(widget, "What is the placement percentage?");
  assert(verified.body.message.confidence === "verified", "Verified placement metric was not used");
  assert(verified.body.message.content.includes("92%"), "Verified placement answer omitted 92%");
  assert(verified.body.message.citations.some((item) => item.title === "Official Placement Report"), "Placement citation was missing");

  const deletedMetric = await adminApi(admin, `/api/v1/admin/metrics/${createdMetric.id}`, { method: "DELETE" });
  assert(deletedMetric.ok, "Could not delete the placement metric");
  const deletedFallback = await chatFromWidget(widget, "What is the placement percentage?");
  assert(deletedFallback.body.message.confidence === "low" && !deletedFallback.body.message.content.includes("0%"), "Deleted metric did not restore safe fallback");

  await clickText(admin, "FAQs");
  await admin.waitForSelector('input[aria-label="Verified FAQ question"]');
  const faqQuestion = "What is the CIET live browser verification code?";
  const faqAnswer = "The verified CIET live browser code is GREEN-LAUNCH.";
  await setInput(admin, 'input[aria-label="Verified FAQ question"]', faqQuestion);
  await setInput(admin, 'input[aria-label="Verified FAQ answer"]', faqAnswer);
  await setInput(admin, 'input[aria-label="FAQ source"]', "CIET E2E Registrar Record");
  await clickText(admin, "Add FAQ");
  const createdFaq = await poll(async () => {
    const response = await adminApi(admin, "/api/v1/admin/faqs");
    return response.body?.find((faq) => faq.question === faqQuestion);
  }, "created FAQ");
  faqId = createdFaq.id;
  const faqChat = await chatFromWidget(widget, faqQuestion);
  assert(faqChat.body.route === "faq" && faqChat.body.message.content === faqAnswer, "Live FAQ retrieval failed");
  // Citations are deliberately no longer rendered inside the chat bubble
  // (clean answer only), so the source guarantee is asserted on the API
  // response, which still carries every citation the retrieval produced.
  assert(
    (faqChat.body.message.citations || []).some(
      (item) => `${item.title}${item.section || ""}`.includes("CIET E2E Registrar Record"),
    ),
    "Live FAQ answer did not carry its source citation through the API",
  );

  await widget.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const launcher = root?.querySelector(".ciet-launcher");
    if (launcher instanceof HTMLElement) launcher.click();
  });
  await widget.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector("textarea"));
  await widget.evaluate((question) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const textarea = root?.querySelector("textarea");
    if (!(textarea instanceof HTMLTextAreaElement)) throw new Error("Widget message field is missing");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(textarea, question);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.closest("form")?.requestSubmit();
  }, faqQuestion);
  await widget.waitForFunction((answer) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return root?.textContent?.includes(answer);
  }, { timeout: 30000 }, faqAnswer);
  const widgetJourney = await widget.evaluate((answer) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return {
      userMessage: [...(root?.querySelectorAll(".ciet-message--user") || [])].some((item) => item.textContent?.includes("verification code")),
      assistantMessage: [...(root?.querySelectorAll(".ciet-message--assistant") || [])].some((item) => item.textContent?.includes(answer)),
    };
  }, faqAnswer);
  assert(widgetJourney.userMessage && widgetJourney.assistantMessage, "Widget message rendering failed");

  const widgetAxe = assertNoSeriousAxeViolations(
    await new AxePuppeteer(widget).analyze(),
    "Widget",
  );
  const adminAxe = assertNoSeriousAxeViolations(
    await new AxePuppeteer(admin).analyze(),
    "Admin",
  );

  const accessibilityControls = await widget.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const feedback = [...(root?.querySelectorAll(".ciet-message-actions button") || [])]
      .map((item) => item.getAttribute("aria-label"))
      .filter(Boolean);
    return { feedback };
  });
  assert(accessibilityControls.feedback.length >= 4, "Feedback/message controls do not have accessible names");

  await widget.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    // NOTE: `.ciet-header-actions button:last-child` also matches the language
    // trigger (it is the only child of .ciet-language) and comes first in
    // document order, so select the final header button — the close control.
    const buttons = [...(root?.querySelectorAll(".ciet-header-actions button") || [])];
    const close = buttons[buttons.length - 1];
    if (close instanceof HTMLElement) close.click();
  });
  await widget.waitForFunction(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return root?.querySelector(".ciet-launcher") && !root.querySelector(".ciet-panel");
  });

  await widget.evaluate(() => {
    const launcher = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-launcher");
    if (launcher instanceof HTMLElement) launcher.focus();
  });
  await widget.keyboard.press("Enter");
  await widget.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.activeElement?.matches("textarea"));
  await widget.keyboard.press("Tab");
  const tabReachedControl = await widget.evaluate(() => {
    const active = document.querySelector("ciet-ai-assistant")?.shadowRoot?.activeElement;
    return Boolean(active?.matches("button,select,textarea,a[href]"));
  });
  assert(tabReachedControl, "TAB did not move to a widget control");
  await widget.keyboard.down("Shift");
  await widget.keyboard.press("Tab");
  await widget.keyboard.up("Shift");
  await widget.keyboard.press("Escape");
  await widget.waitForFunction(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return root?.activeElement?.matches(".ciet-launcher") && !root.querySelector(".ciet-panel");
  });

  const personaQuestions = [
    ["student", faqQuestion, "en"],
    ["parent", "What is the admission process?", "en"],
    ["prospective student", "What courses are available at CIET?", "en"],
    ["faculty", "Where can faculty find official CIET information?", "en"],
    ["website visitor", "How can I contact CIET?", "en"],
  ];
  for (const [persona, question, language] of personaQuestions) {
    const response = await chatFromWidget(widget, question, language);
    assert(response.status === 200 && response.body?.message?.content, `${persona} browser request failed`);
  }

  await clickText(admin, "Documents");
  const fixture = path.resolve("e2e/fixtures/CIET_QA_RAG.txt");
  const existingDocs = await adminApi(admin, "/api/v1/admin/documents");
  for (const document of existingDocs.body.filter((item) => item.title === "CIET_QA_RAG.txt")) {
    await adminApi(admin, `/api/v1/admin/documents/${document.id}`, { method: "DELETE" });
  }
  const upload = await admin.$('input[type="file"]');
  assert(upload, "Document upload input is missing");
  await upload.uploadFile(fixture);
  const processedDocument = await poll(async () => {
    const response = await adminApi(admin, "/api/v1/admin/documents");
    const document = response.body?.find((item) => item.title === "CIET_QA_RAG.txt");
    return ["indexed", "failed"].includes(document?.status) ? document : null;
  }, "document processing");
  documentId = processedDocument.id;
  const reprocess = await adminApi(admin, `/api/v1/admin/documents/${documentId}/reprocess`, { method: "POST" });
  assert(reprocess.ok, "Document reprocess request failed");
  if (processedDocument.status === "failed") {
    assert(processedDocument.error_message, "Failed ingestion did not expose a safe admin error");
    const failedJob = await poll(async () => {
      const response = await adminApi(admin, `/api/v1/admin/documents/${documentId}/job`);
      return response.body?.status === "failed" ? response.body : null;
    }, "failed document reprocessing");
    assert(failedJob.error_message, "Failed reprocessing did not retain an error");
    ingestionMode = "pinecone-unavailable";
  } else {
    await poll(async () => {
      const response = await adminApi(admin, `/api/v1/admin/documents/${documentId}/job`);
      if (response.body?.status === "failed") throw new Error("Live document reprocessing failed");
      return response.body?.status === "complete";
    }, "document reprocessing");
    ingestionMode = "pinecone-indexed";
  }

  await clickText(admin, "Logs");
  const conversations = await adminApi(admin, "/api/v1/admin/conversations");
  assert(
    conversations.ok && conversations.body.some((message) => message.content.includes("placement percentage")),
    "Live conversation logs omitted the placement journey",
  );
  await admin.waitForFunction(() => document.body.innerText.includes("Conversation Logs"));

  for (const width of [375, 414, 768, 1024, 1440]) {
    await widget.setViewport({ width, height: width < 700 ? 844 : 1000 });
    await widget.evaluate(() => {
      const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
      const launcher = root?.querySelector(".ciet-launcher");
      if (launcher instanceof HTMLElement) launcher.click();
    });
    const geometry = await widget.evaluate(() => {
      const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
      const panel = root?.querySelector(".ciet-panel")?.getBoundingClientRect();
      const unnamed = [...(root?.querySelectorAll("button,input,select,textarea,a[href]") || [])].filter((element) => {
        const label = element.getAttribute("aria-label") || element.getAttribute("title") || element.textContent;
        return !label?.trim();
      }).length;
      return { viewport: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, panel: panel ? { left: panel.left, right: panel.right } : null, unnamed };
    });
    assert(geometry.scroll <= geometry.viewport + 1, `Widget host overflow at ${width}px`);
    assert(geometry.panel && geometry.panel.left >= -1 && geometry.panel.right <= width + 1, `Widget panel outside ${width}px viewport`);
    assert(geometry.unnamed === 0, `Widget has unnamed controls at ${width}px`);
    await safeScreenshot(widget, path.join(evidenceDir, `widget-${width}.png`), `widget-${width}`);
  }

  await widget.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const select = root?.querySelector("select");
    if (select instanceof HTMLSelectElement) {
      select.value = "hi";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    }
  });
  await widget.waitForFunction(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return root?.querySelector("textarea")?.getAttribute("aria-label")?.length;
  });

  for (const width of [375, 414, 768, 1024, 1440]) {
    await admin.setViewport({ width, height: width < 700 ? 896 : 1000 });
    const overflow = await admin.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    assert(!overflow, `Admin overflow at ${width}px`);
    // Viewport capture: the dashboard fits the viewport (the logs table is
    // height-capped) and full-page capture of the sticky sidebar times out.
    await safeScreenshot(admin, path.join(evidenceDir, `admin-${width}.png`), `admin-${width}`, { fullPage: false });
  }

  const browserFailureList = [
    ...browserIssues.admin.failures.map((issue) => `admin ${issue}`),
    ...browserIssues.widget.failures.map((issue) => `widget ${issue}`),
  ];
  const browserWarningList = [
    ...browserIssues.admin.warnings.map((issue) => `admin ${issue}`),
    ...browserIssues.widget.warnings.map((issue) => `widget ${issue}`),
  ];
  assert(browserFailureList.length === 0, `Browser reported errors: ${browserFailureList.join(" | ")}`);

  console.log(JSON.stringify({
    result: "Live E2E passed",
    coverage: "real API/PostgreSQL/Redis/Celery, five user perspectives, Shadow DOM message/citation/feedback, keyboard TAB/SHIFT+TAB/ENTER/ESC, focus return, placement lifecycle, FAQ CRUD, upload/reprocess failure-or-success, logs, five responsive viewports",
    ingestionMode,
    browserConsoleAndNetwork: { failures: browserFailureList, warnings: browserWarningList },
    axe: { widget: widgetAxe, admin: adminAxe },
  }));
} finally {
  if (admin && !admin.isClosed()) {
    if (documentId) await adminApi(admin, `/api/v1/admin/documents/${documentId}`, { method: "DELETE" }).catch(() => undefined);
    if (faqId) await adminApi(admin, `/api/v1/admin/faqs/${faqId}`, { method: "DELETE" }).catch(() => undefined);
    const current = await adminApi(admin, "/api/v1/admin/metrics").catch(() => ({ body: [] }));
    const currentMetrics = Array.isArray(current.body) ? current.body : [];
    for (const metric of currentMetrics.filter((item) => item.name.trim().toLowerCase() === "placement percentage")) {
      await adminApi(admin, `/api/v1/admin/metrics/${metric.id}`, { method: "DELETE" }).catch(() => undefined);
    }
    for (const backup of placementBackups) {
      await adminApi(admin, "/api/v1/admin/metrics", {
        method: "POST",
        body: JSON.stringify({ name: backup.name, value: backup.value, unit: backup.unit, verified_by: backup.verified_by, source: backup.source, is_sensitive_stat: backup.is_sensitive_stat }),
      }).catch(() => undefined);
    }
  }
  await browser.close();
}
