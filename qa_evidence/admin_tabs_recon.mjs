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
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
const network = [];
const consoleMessages = [];
const pageErrors = [];
page.on('console', message => consoleMessages.push({ type: message.type(), text: message.text() }));
page.on('pageerror', error => pageErrors.push(error.message));
page.on('response', async response => {
  if (!response.url().includes('localhost:8001/api/') || response.url().endsWith('/auth/login')) return;
  let body = '';
  try { body = (await response.text()).slice(0, 3000); } catch {}
  network.push({ method: response.request().method(), url: response.url(), status: response.status(), body });
});

async function clickButton(text) {
  const clicked = await page.$$eval('button', (buttons, expected) => {
    const button = buttons.find(item => item.innerText.trim() === expected);
    if (!button) return false;
    button.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`Button not found: ${text}`);
}

async function snapshot(name) {
  await new Promise(resolve => setTimeout(resolve, 900));
  await page.screenshot({ path: new URL(`./admin-${name.toLowerCase()}-1440.png`, screenshots).pathname, fullPage: true });
  return page.evaluate(() => ({
    bodyText: document.body.innerText.slice(0, 16000),
    controls: [...document.querySelectorAll('button,input,textarea,select,a')].map((el, index) => ({
      index,
      tag: el.tagName,
      text: el.innerText?.trim(),
      type: el.getAttribute('type'),
      accept: el.getAttribute('accept'),
      placeholder: el.getAttribute('placeholder'),
      ariaLabel: el.getAttribute('aria-label'),
      value: el.type === 'password' ? '[redacted]' : el.value,
      disabled: Boolean(el.disabled),
    })),
  }));
}

await page.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
const inputs = await page.$$('input');
await inputs[0].focus();
await page.keyboard.down('Control');
await page.keyboard.press('KeyA');
await page.keyboard.up('Control');
await page.keyboard.press('Backspace');
await inputs[0].type('cietadmin');
await inputs[1].type('CIET-QA-2026!Strong');
await clickButton('Sign in');
await new Promise(resolve => setTimeout(resolve, 1200));

const tabs = {};
for (const name of ['Dashboard', 'Documents', 'FAQs', 'Metrics', 'Logs', 'Feedback']) {
  await clickButton(name);
  tabs[name] = await snapshot(name);
}

const report = { tabs, network, consoleMessages, pageErrors };
await browser.close();
await fs.writeFile(new URL('./admin-tabs-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
