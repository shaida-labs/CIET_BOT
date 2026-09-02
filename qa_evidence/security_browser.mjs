import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const screenshots = new URL('./screenshots/', base);
const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const report = { loginInjection: {}, repeatBootstrap: {}, unauthenticatedAdmin: {}, console: [], pageErrors: [] };
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1000 });
page.on('console', message => report.console.push({ type: message.type(), text: message.text() }));
page.on('pageerror', error => report.pageErrors.push(error.message));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
async function clearAndType(input, value) {
  await input.focus();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await input.type(value);
}
async function click(text) {
  await page.$$eval('button', (buttons, expected) => buttons.find(button => button.innerText.trim() === expected)?.click(), text);
}

await page.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
let inputs = await page.$$('input');
await clearAndType(inputs[0], "cietadmin' OR '1'='1' --");
await clearAndType(inputs[1], 'invalid');
let responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/login') && response.request().method() === 'POST');
await click('Sign in');
let response = await responsePromise;
report.loginInjection = {
  status: response.status(),
  body: await response.text(),
  visibleText: await page.evaluate(() => document.body.innerText),
};
await page.screenshot({ path: new URL('./security-sql-login.png', screenshots).pathname, fullPage: true });

inputs = await page.$$('input');
await clearAndType(inputs[0], 'secondadmin');
await clearAndType(inputs[1], 'Second-CIET-Admin-2026!');
responsePromise = page.waitForResponse(response => response.url().endsWith('/api/v1/auth/bootstrap') && response.request().method() === 'POST');
await click('Bootstrap first admin');
response = await responsePromise;
report.repeatBootstrap = {
  status: response.status(),
  body: await response.text(),
  visibleText: await page.evaluate(() => document.body.innerText),
};
await page.screenshot({ path: new URL('./security-repeat-bootstrap.png', screenshots).pathname, fullPage: true });

const unauth = await browser.newPage();
response = await unauth.goto('http://localhost:8001/api/v1/admin/analytics', { waitUntil: 'networkidle2', timeout: 30000 });
report.unauthenticatedAdmin = { status: response.status(), body: await response.text() };
await unauth.close();

await browser.close();
await fs.writeFile(new URL('./security-browser-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
