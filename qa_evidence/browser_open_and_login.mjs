import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const screenshots = new URL('./screenshots/', base);
await fs.mkdir(screenshots, { recursive: true });
const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});

async function observe(page) {
  return page.evaluate(() => ({
    url: location.href,
    title: document.title,
    bodyText: document.body.innerText.slice(0, 12000),
    controls: [...document.querySelectorAll('button,input,textarea,select,a')].map((el, index) => ({
      index,
      tag: el.tagName,
      text: el.innerText?.trim(),
      type: el.getAttribute('type'),
      placeholder: el.getAttribute('placeholder'),
      ariaLabel: el.getAttribute('aria-label'),
      value: el.type === 'password' ? '[redacted]' : el.value,
      disabled: Boolean(el.disabled),
    })),
  }));
}

function instrument(page) {
  const evidence = { console: [], pageErrors: [], failedRequests: [], errorResponses: [], api: [] };
  page.on('console', message => evidence.console.push({ type: message.type(), text: message.text() }));
  page.on('pageerror', error => evidence.pageErrors.push(error.message));
  page.on('requestfailed', request => evidence.failedRequests.push({ url: request.url(), error: request.failure()?.errorText }));
  page.on('response', async response => {
    if (response.status() >= 400) evidence.errorResponses.push({ url: response.url(), status: response.status() });
    if (response.url().includes('localhost:8001/api/')) {
      let body = '';
      try { body = (await response.text()).slice(0, 2000); } catch {}
      if (response.url().endsWith('/auth/login')) {
        try {
          const parsed = JSON.parse(body);
          if (parsed.access_token) parsed.access_token = '[redacted-valid-jwt]';
          body = JSON.stringify(parsed);
        } catch {}
      }
      evidence.api.push({ method: response.request().method(), url: response.url(), status: response.status(), body });
    }
  });
  return evidence;
}

const report = {};

{
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  const evidence = instrument(page);
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 30000 });
  await page.click('button[aria-label="Open CIET AI Assistant"]');
  await new Promise(resolve => setTimeout(resolve, 1000));
  await page.screenshot({ path: new URL('./widget-chat-open-1440.png', screenshots).pathname, fullPage: true });
  report.widget = { evidence, ui: await observe(page) };
  await page.close();
}

{
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  const evidence = instrument(page);
  await page.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
  const inputs = await page.$$('input');
  await inputs[0].focus();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await inputs[0].type('cietadmin');
  await inputs[1].type('CIET-QA-2026!Strong');
  await page.click('button');
  await new Promise(resolve => setTimeout(resolve, 1800));
  await page.screenshot({ path: new URL('./admin-after-login-1440.png', screenshots).pathname, fullPage: true });
  report.admin = { evidence, ui: await observe(page) };
  await page.close();
}

await browser.close();
await fs.writeFile(new URL('./open-login-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
