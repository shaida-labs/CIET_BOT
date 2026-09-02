import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const outputDir = new URL('./screenshots/', import.meta.url);
await fs.mkdir(outputDir, { recursive: true });

const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

const report = {};
for (const target of [
  { name: 'widget', url: 'http://localhost:5173' },
  { name: 'admin', url: 'http://localhost:5174' },
]) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000, deviceScaleFactor: 1 });
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  const errorResponses = [];
  page.on('console', message => consoleMessages.push({ type: message.type(), text: message.text() }));
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('requestfailed', request => failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
  page.on('response', response => {
    if (response.status() >= 400) errorResponses.push({ url: response.url(), status: response.status() });
  });
  const started = performance.now();
  const response = await page.goto(target.url, { waitUntil: 'networkidle2', timeout: 30000 });
  const loadMs = Math.round(performance.now() - started);
  await page.screenshot({ path: new URL(`${target.name}-1440.png`, outputDir).pathname, fullPage: true });
  const ui = await page.evaluate(() => ({
    title: document.title,
    bodyText: document.body.innerText.slice(0, 8000),
    inputs: [...document.querySelectorAll('input, textarea, select')].map(el => ({
      tag: el.tagName,
      type: el.getAttribute('type'),
      name: el.getAttribute('name'),
      placeholder: el.getAttribute('placeholder'),
      ariaLabel: el.getAttribute('aria-label'),
    })),
    buttons: [...document.querySelectorAll('button')].map(el => ({
      text: el.innerText.trim(),
      ariaLabel: el.getAttribute('aria-label'),
      title: el.getAttribute('title'),
      disabled: el.disabled,
    })),
    links: [...document.querySelectorAll('a')].map(el => ({ text: el.innerText.trim(), href: el.href })),
  }));
  report[target.name] = {
    initialStatus: response?.status(),
    finalUrl: page.url(),
    loadMs,
    consoleMessages,
    pageErrors,
    failedRequests,
    errorResponses,
    ui,
  };
  await page.close();
}

await browser.close();
await fs.writeFile(new URL('./recon-report.json', import.meta.url), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
