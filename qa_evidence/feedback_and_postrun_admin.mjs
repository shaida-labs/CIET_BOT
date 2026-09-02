import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const screenshots = new URL('./screenshots/', base);
const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const report = { feedback: {}, admin: {} };
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

{
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  const api = [];
  page.on('response', async response => {
    if (!response.url().includes('localhost:8001/api/')) return;
    let body = '';
    try { body = (await response.text()).slice(0, 3000); } catch {}
    api.push({ method: response.request().method(), url: response.url(), status: response.status(), body });
  });
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 30000 });
  await page.click('button[aria-label="Open CIET AI Assistant"]');
  const textarea = await page.$('textarea');
  await textarea.type('What courses are available?');
  const chatResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/api/v1/chat'));
  await page.click('button[type="submit"]');
  await chatResponse;
  await delay(400);
  const controls = await page.evaluate(() => [...document.querySelectorAll('button')].map((button, index) => ({
    index,
    text: button.innerText.trim(),
    ariaLabel: button.getAttribute('aria-label'),
    title: button.getAttribute('title'),
  })));
  const helpful = controls.find(control => /helpful|thumbs up|positive/i.test(`${control.ariaLabel} ${control.title}`) && !/not helpful|thumbs down|negative/i.test(`${control.ariaLabel} ${control.title}`));
  if (helpful) {
    const feedbackResponse = page.waitForResponse(response => response.request().method() === 'POST' && response.url().includes('/feedback'));
    await page.$$eval('button', (buttons, index) => buttons[index]?.click(), helpful.index);
    await feedbackResponse.catch(() => null);
    await delay(300);
  }
  await page.screenshot({ path: new URL('./feedback-submitted.png', screenshots).pathname, fullPage: true });
  report.feedback = { controls, helpfulControlFound: Boolean(helpful), api, bodyText: await page.evaluate(() => document.body.innerText) };
  await page.close();
}

{
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
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
  await delay(1000);
  report.admin.dashboard = await page.evaluate(() => document.body.innerText);
  await page.screenshot({ path: new URL('./admin-dashboard-postrun.png', screenshots).pathname, fullPage: true });
  for (const tab of ['Logs', 'Feedback']) {
    await page.$$eval('button', (buttons, text) => buttons.find(button => button.innerText.trim() === text)?.click(), tab);
    await delay(800);
    report.admin[tab.toLowerCase()] = await page.evaluate(() => document.body.innerText.slice(0, 20000));
    await page.screenshot({ path: new URL(`./admin-${tab.toLowerCase()}-postrun.png`, screenshots).pathname, fullPage: true });
  }
  await page.close();
}

await browser.close();
await fs.writeFile(new URL('./feedback-postrun-admin-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
