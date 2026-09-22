import { spawn } from "node:child_process";
import puppeteer from "puppeteer";

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const servers = [
  spawn(npmCmd, ["run", "dev", "-w", "@ciet/widget", "--", "--host", "127.0.0.1", "--port", "5173"], { stdio: "inherit", shell: true }),
  spawn(npmCmd, ["run", "dev", "-w", "@ciet/admin", "--", "--host", "127.0.0.1", "--port", "5174"], { stdio: "inherit", shell: true }),
];

async function waitFor(url) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch { /* server is still starting */ }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Timed out waiting for ${url}`);
}

const corsHeaders = {
  "Access-Control-Allow-Origin": "http://127.0.0.1:5174",
  "Access-Control-Allow-Credentials": "true",
  "Access-Control-Allow-Headers": "Content-Type,X-CIET-Tenant,X-CSRF-Token",
  "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
  "Content-Type": "application/json",
};

async function mockApi(page) {
  await page.setRequestInterception(true);
  page.on("request", async (request) => {
    const url = new URL(request.url());
    if (url.port !== "8000" && !url.pathname.startsWith("/api/")) return request.continue();
    corsHeaders["Access-Control-Allow-Origin"] = request.headers().origin || "http://127.0.0.1:5174";
    if (request.method() === "OPTIONS") return request.respond({ status: 204, headers: corsHeaders });
    const path = url.pathname;
    if (path.endsWith("/auth/login")) return request.respond({ status: 200, headers: corsHeaders, body: JSON.stringify({ authenticated: true, challenge: "chal-123456", otp_required: true }) });
    if (path.endsWith("/auth/otp/verify")) return request.respond({ status: 200, headers: corsHeaders, body: JSON.stringify({ authenticated: true, email: "admin@ciet.edu", role: "super_admin" }) });
    if (path.endsWith("/admin/analytics")) return request.respond({ status: 200, headers: corsHeaders, body: JSON.stringify({ total_queries: 8, failed_queries: 1, avg_response_ms: 42, website_usage: 7, whatsapp_usage: 1, user_satisfaction: 0.9, popular_questions: [], document_usage: [] }) });
    if (path.endsWith("/admin/faqs")) return request.respond({ status: 200, headers: corsHeaders, body: JSON.stringify([{ id: "faq-1", question: "How do admissions work?", answer: "Apply through the official process.", language: "en", source: "Registrar", is_active: true, updated_at: new Date().toISOString() }]) });
    if (path.endsWith("/admin/metrics")) return request.respond({ status: 200, headers: corsHeaders, body: "[]" });
    if (path.endsWith("/admin/documents")) return request.respond({ status: 200, headers: corsHeaders, body: "[]" });
    if (path.endsWith("/admin/conversations")) return request.respond({ status: 200, headers: corsHeaders, body: "[]" });
    if (path.endsWith("/admin/feedback")) return request.respond({ status: 200, headers: corsHeaders, body: JSON.stringify([{ id: "feedback-1", message_id: "message-1", rating: "up", message_content: "Verified answer", conversation_id: "conversation-1", created_at: new Date().toISOString() }]) });
    if (path.endsWith("/feedback")) return request.respond({ status: 204, headers: corsHeaders });
    if (path.endsWith("/chat")) {
      const payload = JSON.parse(request.postData() || "{}");
      const answers = { en: "Verified test answer", te: "ధృవీకరించిన పరీక్ష సమాధానం", hi: "सत्यापित परीक्षण उत्तर" };
      return request.respond({ status: 200, headers: { ...corsHeaders, "Access-Control-Allow-Origin": "http://127.0.0.1:5173" }, body: JSON.stringify({ conversation_id: "conversation-1", route: "faq", message: { id: "message-1", role: "assistant", content: answers[payload.language] || answers.en, created_at: new Date().toISOString(), confidence: "verified", citations: [{ title: "Registrar FAQ" }] } }) });
    }
    return request.respond({ status: 404, headers: corsHeaders, body: JSON.stringify({ detail: "Not mocked" }) });
  });
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function assertAccessibleControls(page, context) {
  const unnamed = await page.evaluate(() => [...document.querySelectorAll("button, input, select, textarea, a[href]")]
    .filter((element) => !(element instanceof HTMLInputElement && element.type === "hidden"))
    .filter((element) => {
      const label = element.getAttribute("aria-label")
        || element.getAttribute("title")
        || ("labels" in element && element.labels?.[0]?.textContent)
        || element.textContent;
      return !label?.trim();
    })
    .map((element) => element.outerHTML.slice(0, 160)));
  assert(unnamed.length === 0, `${context} has unnamed controls: ${unnamed.join(", ")}`);
}

try {
  await Promise.all([waitFor("http://127.0.0.1:5173"), waitFor("http://127.0.0.1:5174")]);
  const browser = await puppeteer.launch({ headless: true, executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined, args: ["--no-sandbox", "--disable-dev-shm-usage"] });

  const widget = await browser.newPage();
  await mockApi(widget);
  for (const width of [375, 414]) {
    await widget.setViewport({ width, height: 844 });
    await widget.goto("http://127.0.0.1:5173", { waitUntil: "networkidle2" });
    const launcher = await widget.$('button[aria-label="Open CIET AI Assistant"]');
    assert(launcher, `widget launcher missing at ${width}px`);
    await launcher.click();
    await assertAccessibleControls(widget, `widget at ${width}px`);
    const geometry = await widget.evaluate(() => {
      const panel = document.querySelector("#ciet-ai-root")?.querySelector(".ciet-panel")?.getBoundingClientRect();
      return { viewport: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth, panel: panel ? { left: panel.left, right: panel.right } : null };
    });
    assert(geometry.scroll <= geometry.viewport + 1, `widget overflow at ${width}px`);
    assert(geometry.panel && geometry.panel.left >= -1 && geometry.panel.right <= width + 1, `widget panel outside ${width}px viewport`);
  }
  await widget.type("textarea", "Tell me about admissions");
  await widget.keyboard.press("Enter");
  await widget.waitForSelector(".ciet-message-actions");
  const feedbackButton = await widget.$('button[aria-label="Helpful answer"]');
  await feedbackButton.click();
  await widget.waitForFunction(() => document.body.innerText.includes("Your feedback was saved"));
  await widget.close();

  const admin = await browser.newPage();
  await mockApi(admin);
  await admin.setViewport({ width: 414, height: 896 });
  await admin.goto("http://127.0.0.1:5174", { waitUntil: "networkidle2" });
  assert(await admin.$("form input[type=password]"), "password input is not part of a form");
  await assertAccessibleControls(admin, "admin login");
  await admin.type("input[type=email]", "admin@ciet.edu");
  await admin.type("input[type=password]", "browser-test-password");
  await admin.click('button[type="submit"]');
  await admin.waitForSelector("#admin-otp");
  await assertAccessibleControls(admin, "admin otp");
  await admin.type("#admin-otp", "123456");
  await admin.click('button[type="submit"]');
  await admin.waitForSelector(".shell");
  await assertAccessibleControls(admin, "admin dashboard");
  for (const width of [375, 414]) {
    await admin.setViewport({ width, height: 896 });
    const geometry = await admin.evaluate(() => ({ viewport: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    assert(geometry.scroll <= geometry.viewport + 1, `admin overflow at ${width}px`);
  }
  await admin.evaluate(() => [...document.querySelectorAll("button")].find((button) => button.textContent?.includes("FAQs"))?.click());
  await admin.waitForFunction(() => document.body.innerText.includes("Edit"));
  await admin.evaluate(() => [...document.querySelectorAll("button")].find((button) => button.textContent?.includes("Feedback"))?.click());
  await admin.waitForFunction(() => document.body.innerText.includes("Verified answer"));
  await admin.close();
  await browser.close();
  console.log("E2E readiness checks passed: widget feedback + admin FAQ/feedback + 375/414 responsive layouts + accessible control names.");
} finally {
  for (const server of servers) server.kill("SIGTERM");
}
