import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const browser = await puppeteer.launch({ headless: true, executablePath: '/usr/bin/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
const responses = [];
page.on('response', async response => {
  if (!response.url().endsWith('/api/v1/admin/analytics')) return;
  let body = '';
  try { body = await response.text(); } catch {}
  responses.push({ method: response.request().method(), status: response.status(), body });
});
await page.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
const inputs = await page.$$('input');
await inputs[0].focus();
await page.keyboard.down('Control');
await page.keyboard.press('KeyA');
await page.keyboard.up('Control');
await page.keyboard.press('Backspace');
await inputs[0].type('cietadmin');
await inputs[1].type('CIET-QA-2026!Strong');
await page.$$eval('button', buttons => buttons.find(button => button.innerText.trim() === 'Sign in')?.click());
await new Promise(resolve => setTimeout(resolve, 1400));
const report = { responses, visibleText: await page.evaluate(() => document.body.innerText) };
await page.screenshot({ path: new URL('./screenshots/admin-analytics-verify.png', base).pathname, fullPage: true });
await browser.close();
await fs.writeFile(new URL('./admin-analytics-verify-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
