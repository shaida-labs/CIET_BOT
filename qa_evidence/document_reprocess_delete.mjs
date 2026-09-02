import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const screenshots = new URL('./screenshots/', base);
const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
page.on('dialog', dialog => dialog.accept());
const report = { network: [], console: [], pageErrors: [], states: {} };
page.on('console', message => report.console.push({ type: message.type(), text: message.text() }));
page.on('pageerror', error => report.pageErrors.push(error.message));
page.on('response', async response => {
  if (!response.url().includes('localhost:8001/api/') || response.url().endsWith('/auth/login')) return;
  let body = '';
  try { body = (await response.text()).slice(0, 4000); } catch {}
  report.network.push({ method: response.request().method(), url: response.url(), status: response.status(), body });
});
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function clickButton(text) {
  const clicked = await page.$$eval('button', (buttons, expected) => {
    const button = buttons.find(item => item.innerText.trim() === expected);
    if (!button) return false;
    button.click();
    return true;
  }, text);
  if (!clicked) throw new Error(`Button not found: ${text}`);
}
async function state() {
  return page.evaluate(() => ({
    bodyText: document.body.innerText,
    buttons: [...document.querySelectorAll('button')].map(button => button.innerText.trim()),
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
await delay(1000);
await clickButton('Documents');
await delay(700);
report.states.before = await state();
await clickButton('Reprocess');
await delay(2500);
report.states.afterReprocess = await state();
await page.screenshot({ path: new URL('./document-reprocessed.png', screenshots).pathname, fullPage: true });
await clickButton('Delete');
await delay(900);
report.states.afterDelete = await state();
await page.screenshot({ path: new URL('./document-deleted.png', screenshots).pathname, fullPage: true });

await browser.close();
await fs.writeFile(new URL('./document-reprocess-delete-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
