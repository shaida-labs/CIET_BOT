import { mkdir } from "node:fs/promises";
import path from "node:path";
import puppeteer from "puppeteer";

const webUrl = process.env.CIET_E2E_WEB_URL || "http://localhost:8080";
const evidenceDir = path.resolve("qa_evidence/screenshots/widget-i18n");

const scenarios = [
  { language: "en", question: "Where is CIET located?", answerFragment: "CIET" },
  { language: "te", question: "CIET ఎక్కడ ఉంది?", answerFragment: "ఈ ప్రశ్నకు" },
  { language: "hi", question: "CIET कहाँ स्थित है?", answerFragment: "इस प्रश्न के" },
];

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function openWidget(page) {
  await page.goto(`${webUrl}/widget/embed-test.html`, { waitUntil: "networkidle2" });
  await page.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot);
  await page.evaluate(() => {
    const launcher = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-launcher");
    if (!(launcher instanceof HTMLElement)) throw new Error("Widget launcher was not mounted");
    launcher.click();
  });
  await page.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-panel"));
}

async function chooseLanguage(page, language) {
  await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const trigger = root?.querySelector(".ciet-language-trigger");
    if (!(trigger instanceof HTMLElement)) throw new Error("Language selector was not mounted");
    trigger.click();
  });
  await page.waitForFunction((nextLanguage) => Boolean(
    document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(`[data-language="${nextLanguage}"]`),
  ), {}, language);
  await page.evaluate((nextLanguage) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const option = root?.querySelector(`[data-language="${nextLanguage}"]`);
    if (!(option instanceof HTMLElement)) throw new Error(`Language option ${nextLanguage} was not mounted`);
    option.click();
  }, language);
  await page.waitForFunction((expected) => {
    const widget = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-widget");
    return widget?.getAttribute("lang") === expected;
  }, {}, language);
}

async function ask(page, question, answerFragment) {
  await page.evaluate((message) => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    const textarea = root?.querySelector("textarea");
    if (!(textarea instanceof HTMLTextAreaElement)) throw new Error("Message input was not mounted");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    setter?.call(textarea, message);
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
    textarea.closest("form")?.requestSubmit();
  }, question);
  await page.waitForFunction((expected) => {
    const messages = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelectorAll(".ciet-message--assistant");
    return [...(messages || [])].some((message) => message.textContent?.includes(expected));
  }, { timeout: 30_000 }, answerFragment);
}

async function assertIndicFonts(page) {
  const fonts = await page.evaluate(async () => {
    await document.fonts.load('16px "Noto Sans Telugu"', "తెలుగు");
    await document.fonts.load('16px "Noto Sans Devanagari"', "हिन्दी");
    await document.fonts.ready;
    return {
      telugu: document.fonts.check('16px "Noto Sans Telugu"', "తెలుగు"),
      hindi: document.fonts.check('16px "Noto Sans Devanagari"', "हिन्दी"),
    };
  });
  assert(fonts.telugu && fonts.hindi, "Self-hosted Indic fonts did not load in the browser");
}

async function assertLayout(page, viewport) {
  const layout = await page.evaluate(() => {
    const panel = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-panel")?.getBoundingClientRect();
    return {
      documentWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      panel: panel && { left: panel.left, right: panel.right, top: panel.top, bottom: panel.bottom },
    };
  });
  assert(layout.scrollWidth <= layout.documentWidth + 1, `Horizontal overflow at ${viewport.width}px`);
  assert(layout.panel, `Panel is missing at ${viewport.width}px`);
  assert(layout.panel.left >= -1 && layout.panel.right <= viewport.width + 1, `Panel overflows at ${viewport.width}px`);
}

await mkdir(evidenceDir, { recursive: true });
const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || "/usr/bin/chromium",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

const failures = [];
try {
  const page = await browser.newPage();
  page.on("console", (entry) => {
    if (entry.type() === "error") {
      const location = entry.location();
      failures.push(`Console error: ${entry.text()} (${location.url || "unknown source"})`);
    }
  });
  page.on("requestfailed", (request) => failures.push(`Request failed: ${request.url()} (${request.failure()?.errorText || "unknown"})`));
  page.on("response", (response) => {
    if (response.status() >= 400) failures.push(`HTTP ${response.status()}: ${response.url()}`);
  });

  const desktop = { width: 1440, height: 960 };
  await page.setViewport(desktop);
  await openWidget(page);
  await assertIndicFonts(page);
  await page.evaluate(() => {
    const trigger = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-language-trigger");
    if (!(trigger instanceof HTMLElement)) throw new Error("Language trigger was not mounted");
    trigger.click();
  });
  await page.waitForFunction(() => Boolean(
    document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-language-menu"),
  ));
  const languageMenu = await page.evaluate(() => [...(
    document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelectorAll(".ciet-language-option") || []
  )].map((option) => ({ language: option.getAttribute("data-language"), label: option.textContent?.trim() })));
  assert(
    JSON.stringify(languageMenu) === JSON.stringify([
      { language: "en", label: "English" },
      { language: "te", label: "తెలుగు" },
      { language: "hi", label: "हिन्दी" },
    ]),
    `Language menu labels are incorrect: ${JSON.stringify(languageMenu)}`,
  );
  await page.screenshot({ path: path.join(evidenceDir, "language-menu.png"), fullPage: true });
  await page.evaluate(() => {
    const trigger = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-language-trigger");
    if (!(trigger instanceof HTMLElement)) throw new Error("Language trigger was not mounted");
    trigger.click();
  });
  for (const scenario of scenarios) {
    await chooseLanguage(page, scenario.language);
    const fontStack = await page.evaluate(() => getComputedStyle(
      document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-widget"),
    ).fontFamily);
    if (scenario.language === "te") assert(fontStack.startsWith('"Noto Sans Telugu"'), "Telugu UI did not select Noto Sans Telugu");
    if (scenario.language === "hi") assert(fontStack.startsWith('"Noto Sans Devanagari"'), "Hindi UI did not select Noto Sans Devanagari");
    await ask(page, scenario.question, scenario.answerFragment);
    await assertLayout(page, desktop);
    await page.screenshot({ path: path.join(evidenceDir, `${scenario.language}-desktop.png`), fullPage: true });
  }
  const preservedMessageLanguages = await page.evaluate(() => {
    const root = document.querySelector("ciet-ai-assistant")?.shadowRoot;
    return {
      telugu: Boolean(root?.querySelector('.ciet-message-row[lang="te"]')),
      hindi: Boolean(root?.querySelector('.ciet-message-row[lang="hi"]')),
    };
  });
  assert(
    preservedMessageLanguages.telugu && preservedMessageLanguages.hindi,
    "Messages must retain their own language metadata after an interface language switch",
  );

  const mobile = { width: 390, height: 844 };
  await page.setViewport(mobile);
  for (const scenario of scenarios) {
    await chooseLanguage(page, scenario.language);
    await assertLayout(page, mobile);
    await page.screenshot({ path: path.join(evidenceDir, `${scenario.language}-mobile.png`), fullPage: true });
  }
  for (const width of [320, 375, 390, 430, 768, 1024, 1440]) {
    const viewport = { width, height: width < 640 ? 844 : 960 };
    await page.setViewport(viewport);
    await assertLayout(page, viewport);
  }
  assert(failures.length === 0, failures.join("\n"));
  console.log("Widget i18n browser checks passed: real API responses, Indic fonts, desktop/mobile layout, and no browser errors.");
} finally {
  await browser.close();
}
