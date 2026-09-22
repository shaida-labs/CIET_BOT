import { mkdir, rm } from "node:fs/promises";
import path from "node:path";
import puppeteer from "puppeteer";

const webUrl = process.env.CIET_E2E_WEB_URL || "http://localhost:8080";
const evidenceDir = path.resolve("qa_evidence/screenshots/ui-smoke");

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

const checks = [];
function check(name, condition, detail = "") {
  checks.push({ name, status: condition ? "PASS" : "FAIL", detail });
  if (!condition) throw new Error(`UI check failed: ${name} ${detail}`);
}

async function openWidget(page) {
  await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const launcher = root.querySelector(".ciet-launcher");
    if (!(launcher instanceof HTMLElement)) throw new Error("Widget launcher was not mounted");
    launcher.click();
  });
  await page.waitForFunction(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return Boolean(root.querySelector(".ciet-panel"));
  });
}

async function submitQuestion(page, question) {
  const answeredBefore = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return root.querySelectorAll(".ciet-message--assistant").length;
  });
  await page.evaluate((message) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const textarea = root.querySelector("textarea");
    if (!(textarea instanceof HTMLTextAreaElement)) throw new Error("Message input was not mounted");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(textarea, message);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.closest("form")?.requestSubmit();
  }, question);
  // Wait for one NEW assistant reply beyond what was already on screen.
  await page.waitForFunction((previous) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return [...root.querySelectorAll(".ciet-message--assistant")].length > previous
      && !root.querySelector(".ciet-typing")
      && !root.querySelector(".ciet-error");
  }, { timeout: 60_000 }, answeredBefore);
}

async function chooseLanguage(page, language) {
  // Open the menu first, then wait for React to mount the options before clicking.
  await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    root.querySelector(".ciet-language-trigger")?.click();
  });
  await page.waitForFunction((next) => Boolean(
    (document.querySelector("ciet-ai-assistant")?.shadowRoot || document).querySelector(`[data-language="${next}"]`),
  ), {}, language);
  await page.evaluate((next) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const option = root.querySelector(`[data-language="${next}"]`);
    if (!(option instanceof HTMLElement)) throw new Error(`Language option ${next} was not mounted`);
    option.click();
  }, language);
  await page.waitForFunction((expected) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const widget = root.querySelector(".ciet-widget");
    return widget?.getAttribute("lang") === expected;
  }, {}, language);
  // The whole conversation, history included, must follow the new language.
  // Allow generous time: the server translates with provider failover, which
  // can sit behind rate limits before it answers.
  await page.waitForFunction((expected) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const rows = [...root.querySelectorAll(".ciet-message-row")];
    return rows.length > 0 && rows.every((row) => row.getAttribute("lang") === expected);
  }, { timeout: 150_000 }, language);
}

await rm(evidenceDir, { recursive: true, force: true });
await mkdir(evidenceDir, { recursive: true });
const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const failures = [];
try {
  const page = await browser.newPage();
  page.on("console", (entry) => {
    if (entry.type() === "error") failures.push(`Console error: ${entry.text()}`);
  });
  page.on("requestfailed", (request) => failures.push(`Request failed: ${request.url()}`));
  page.on("response", (response) => {
    if (response.status() >= 400) failures.push(`HTTP ${response.status()}: ${response.url()}`);
  });
  await page.setViewport({ width: 1440, height: 960 });

  // 1) Clean start: the preview screen must not show the integration scaffold.
  await page.goto(`${webUrl}/widget/`, { waitUntil: "networkidle2" });
  await page.evaluate(() => localStorage.clear());
  await page.reload({ waitUntil: "networkidle2" });
  const landing = await page.evaluate(() => ({
    title: document.title,
    text: document.body.innerText,
    snippet: Boolean(document.getElementById("ciet-preview-snippet")),
  }));
  check("preview title", landing.title === "CIET AI Assistant", landing.title);
  check("no integration scaffold text", !landing.text.includes("CIET AI Widget integration preview"));
  check("no instruction line", !landing.text.includes("Look at the bottom-right corner"));
  check("no embed snippet", !landing.text.includes("ciet-ai.js") && !landing.snippet);
  const launcherPresent = await page.evaluate(() => Boolean(
    (document.querySelector("ciet-ai-assistant")?.shadowRoot || document).querySelector(".ciet-launcher"),
  ));
  check("floating launcher present", launcherPresent);
  await page.screenshot({ path: path.join(evidenceDir, "01-preview-clean.png"), fullPage: true });

  // 2) Open the chat: suggestions are small and only appear before the first query.
  await openWidget(page);
  const before = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const rail = root.querySelector(".ciet-quick-actions");
    const chip = root.querySelector(".ciet-quick-actions button");
    if (!rail || !chip) return null;
    const box = rail.getBoundingClientRect();
    return {
      height: Math.round(box.height),
      fontSize: getComputedStyle(chip).fontSize,
      chips: root.querySelectorAll(".ciet-quick-actions button").length,
    };
  });
  assert(before, "Starter suggestions were not shown before the first query");
  check("suggestions compact", before.height <= 44 && parseFloat(before.fontSize) <= 12,
    JSON.stringify(before));
  check("all nine suggestions available", before.chips === 9, JSON.stringify(before));
  await page.screenshot({ path: path.join(evidenceDir, "02-suggestions-compact.png"), fullPage: true });

  // 3) Ask a real question: the answer must render as clean formatted text.
  await submitQuestion(page, "Which buses stop at Market? Give driver names and departure times in a table.");
  const rendered = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const answers = [...root.querySelectorAll(".ciet-message--assistant")];
    const last = answers[answers.length - 1];
    return {
      text: last?.textContent || "",
      hasTable: Boolean(last?.querySelector("table")),
      markdown: Boolean(last?.querySelector(".ciet-markdown")),
      citations: Boolean(root.querySelector(".ciet-citations")),
      meta: Boolean(root.querySelector(".ciet-message-meta")),
      confidence: Boolean(root.querySelector(".ciet-confidence")),
      trust: Boolean(root.querySelector(".ciet-trust")),
      suggestionsAfterQuery: Boolean(root.querySelector(".ciet-quick-actions")),
      rawBold: (last?.textContent || "").includes("**"),
      rawPipes: /\| {2,}/.test(last?.textContent || ""),
    };
  });
  check("answer is non-trivial", rendered.text.trim().length > 40, rendered.text.slice(0, 80));
  check("markdown container used", rendered.markdown);
  check("answer renders a real table", rendered.hasTable, rendered.text.slice(0, 200));
  check("no raw ** markers", !rendered.rawBold);
  check("no raw markdown table pipes", !rendered.rawPipes);
  check("no citations under the answer", !rendered.citations);
  check("no timestamp/confidence metadata", !rendered.meta && !rendered.confidence);
  check("trust strip removed", !rendered.trust);
  check("suggestions hidden after first query", !rendered.suggestionsAfterQuery);
  await page.screenshot({ path: path.join(evidenceDir, "03-answer-clean.png"), fullPage: true });

  // 4) Question-only answers: one asked fact, nothing the question did not request.
  await submitQuestion(page, "Which time does the bus reach Narakoduru?");
  const concise = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const answers = [...root.querySelectorAll(".ciet-message--assistant")];
    const last = answers[answers.length - 1];
    return (last?.textContent || "").trim();
  });
  check("answer states the stop and the time", /narakoduru/i.test(concise) && /0?8:00/.test(concise), concise);
  check("answer leaves out driver and unrelated details", !/narasimha|driver/i.test(concise), concise);
  check("answer stays a single short reply", concise.length > 10 && concise.length <= 300,
    `${concise.length}: ${concise}`);
  await page.screenshot({ path: path.join(evidenceDir, "04-concise-answer.png"), fullPage: true });

  // 5) Minimize collapses back to the plain launcher icon (as on first open).
  const userRowsBefore = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return root.querySelectorAll(".ciet-message--user").length;
  });
  await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const minimize = root.querySelector('.ciet-header-actions button[aria-label="Minimize assistant"]');
    if (!(minimize instanceof HTMLElement)) throw new Error("Minimize button was not mounted");
    minimize.click();
  });
  await page.waitForFunction(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return !root.querySelector(".ciet-panel") && Boolean(root.querySelector(".ciet-launcher"));
  });
  const collapsed = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return {
      panel: Boolean(root.querySelector(".ciet-panel")),
      minimizedPanel: Boolean(root.querySelector(".ciet-panel--minimized")),
      launcher: Boolean(root.querySelector(".ciet-launcher")),
    };
  });
  check("minimize returns to the launcher icon", !collapsed.panel && !collapsed.minimizedPanel && collapsed.launcher,
    JSON.stringify(collapsed));
  await page.screenshot({ path: path.join(evidenceDir, "05-minimize-to-launcher.png"), fullPage: true });

  await openWidget(page);
  const reopened = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    return {
      panel: Boolean(root.querySelector(".ciet-panel")),
      userRows: root.querySelectorAll(".ciet-message--user").length,
    };
  });
  check("reopening restores the full chat with history intact",
    reopened.panel && reopened.userRows === userRowsBefore && reopened.userRows >= 2,
    JSON.stringify(reopened));

  // 6) Language switch: UI labels AND the entire history must change together.
  await chooseLanguage(page, "te");
  const telugu = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const rows = [...root.querySelectorAll(".ciet-message-row")];
    return {
      langs: rows.map((row) => row.getAttribute("lang")),
      teluguChars: rows.filter((row) => /[ఀ-౿]/.test(row.textContent || "")).length,
      total: rows.length,
      notice: root.querySelector(".ciet-notice--translating")?.textContent || null,
      triggerLabel: root.querySelector(".ciet-language-trigger span")?.textContent || "",
      wrapperMarkup: rows.filter((row) => /<\/?text>/.test(row.textContent || "")).length,
    };
  });
  check("every row switched to Telugu", telugu.langs.length >= 3 && telugu.langs.every((l) => l === "te"),
    JSON.stringify(telugu.langs));
  check("history content translated to Telugu script", telugu.teluguChars >= 3,
    `${telugu.teluguChars}/${telugu.total}`);
  check("language trigger shows Telugu", telugu.triggerLabel.includes("తెలుగు"), telugu.triggerLabel);
  check("no prompt wrapper markup in Telugu history", telugu.wrapperMarkup === 0,
    String(telugu.wrapperMarkup));
  await page.screenshot({ path: path.join(evidenceDir, "06-history-te.png"), fullPage: true });

  await chooseLanguage(page, "hi");
  const hindi = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot || document;
    const rows = [...root.querySelectorAll(".ciet-message-row")];
    return {
      langs: rows.map((row) => row.getAttribute("lang")),
      hindiChars: rows.filter((row) => /[ऀ-ॿ]/.test(row.textContent || "")).length,
      total: rows.length,
      wrapperMarkup: rows.filter((row) => /<\/?text>/.test(row.textContent || "")).length,
    };
  });
  check("every row switched to Hindi", hindi.langs.every((l) => l === "hi"), JSON.stringify(hindi.langs));
  check("history content translated to Devanagari", hindi.hindiChars >= 3, `${hindi.hindiChars}/${hindi.total}`);
  check("no prompt wrapper markup in Hindi history", hindi.wrapperMarkup === 0,
    String(hindi.wrapperMarkup));
  await page.screenshot({ path: path.join(evidenceDir, "07-history-hi.png"), fullPage: true });

  check("no browser/network errors", failures.length === 0, failures.join(" | "));

  console.log(JSON.stringify({ checks, failures }, null, 2));
  console.log(`\nUI smoke walkthrough passed: ${checks.length} checks, screenshots in ${evidenceDir}`);
} catch (error) {
  console.log(JSON.stringify({ checks, failures, error: error.message }, null, 2));
  process.exitCode = 1;
} finally {
  await browser.close();
}
