// Screenshot the HTML email evidence written by
// services/api/scripts/render_email_evidence.py into qa_evidence/emails/.
//
//   cd services/api && .venv\Scripts\python -m scripts.render_email_evidence
//   node e2e/email-evidence.mjs
import { readdir, mkdir } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import puppeteer from "puppeteer";

const evidenceDir = path.resolve("qa_evidence/emails");
await mkdir(evidenceDir, { recursive: true });

const pages = (await readdir(evidenceDir)).filter((name) => name.endsWith(".html"));
if (pages.length === 0) {
  console.error("No HTML files in qa_evidence/emails — run scripts.render_email_evidence first.");
  process.exit(1);
}

const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

try {
  for (const name of pages) {
    const page = await browser.newPage();
    await page.setViewport({ width: 700, height: 1500, deviceScaleFactor: 2 });
    await page.goto(pathToFileURL(path.join(evidenceDir, name)).href, { waitUntil: "networkidle0" });
    const shot = name.replace(/\.html$/, ".png");
    await page.screenshot({ path: path.join(evidenceDir, shot), fullPage: true });
    console.log(`rendered ${shot}`);
    await page.close();
  }
} finally {
  await browser.close();
}
