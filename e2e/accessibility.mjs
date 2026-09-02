import { AxePuppeteer } from "@axe-core/puppeteer";
import puppeteer from "puppeteer";

const WEB_URL = process.env.CIET_E2E_WEB_URL || "http://localhost:8080";
const browser = await puppeteer.launch({
  headless: true,
  executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

try {
  const page = await browser.newPage();
  await page.goto(`${WEB_URL}/widget/embed-test.html`, { waitUntil: "networkidle2" });
  await page.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-launcher"));
  await page.evaluate(() => {
    const launcher = document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector(".ciet-launcher");
    if (launcher instanceof HTMLElement) launcher.click();
  });
  await page.waitForFunction(() => document.querySelector("ciet-ai-assistant")?.shadowRoot?.querySelector("[role=dialog]"));
  const result = await new AxePuppeteer(page).analyze();
  const violations = result.violations.map((item) => ({
    id: item.id,
    impact: item.impact,
    help: item.help,
    nodes: item.nodes.map((node) => ({ target: node.target, failure: node.failureSummary })),
  }));
  console.log(JSON.stringify({ violations }, null, 2));
  if (violations.length) process.exitCode = 1;
} finally {
  await browser.close();
}
