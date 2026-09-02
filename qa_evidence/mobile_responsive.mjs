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
const widths = [375, 414, 768, 1024, 1440];
const report = { widget: {}, admin: {} };

async function layout(page) {
  return page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth;
    const offending = [...document.querySelectorAll('body *')].filter(el => {
      const style = getComputedStyle(el);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
      const rect = el.getBoundingClientRect();
      return rect.right > viewportWidth + 1 || rect.left < -1;
    }).slice(0, 30).map(el => ({
      tag: el.tagName,
      className: String(el.className).slice(0, 180),
      text: el.innerText?.trim().slice(0, 100),
      rect: (() => { const r = el.getBoundingClientRect(); return { left: r.left, right: r.right, width: r.width }; })(),
    }));
    return {
      viewportWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      hasHorizontalOverflow: document.documentElement.scrollWidth > viewportWidth + 1,
      offending,
      bodyText: document.body.innerText.slice(0, 3000),
    };
  });
}

for (const width of widths) {
  const page = await browser.newPage();
  await page.setViewport({ width, height: 900 });
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 30000 });
  await page.click('button[aria-label="Open CIET AI Assistant"]');
  await new Promise(resolve => setTimeout(resolve, 400));
  report.widget[width] = await layout(page);
  await page.screenshot({ path: new URL(`./mobile-widget-${width}.png`, screenshots).pathname, fullPage: true });
  await page.close();
}

const admin = await browser.newPage();
await admin.setViewport({ width: 1440, height: 900 });
await admin.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
const inputs = await admin.$$('input');
await inputs[0].focus();
await admin.keyboard.down('Control');
await admin.keyboard.press('KeyA');
await admin.keyboard.up('Control');
await admin.keyboard.press('Backspace');
await inputs[0].type('cietadmin');
await inputs[1].type('CIET-QA-2026!Strong');
await admin.$$eval('button', buttons => buttons.find(button => button.innerText.trim() === 'Sign in')?.click());
await new Promise(resolve => setTimeout(resolve, 1200));
for (const width of widths) {
  await admin.setViewport({ width, height: 900 });
  await new Promise(resolve => setTimeout(resolve, 300));
  report.admin[width] = await layout(admin);
  await admin.screenshot({ path: new URL(`./mobile-admin-${width}.png`, screenshots).pathname, fullPage: true });
}

await browser.close();
await fs.writeFile(new URL('./mobile-responsive-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
