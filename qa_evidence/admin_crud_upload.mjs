import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';
import path from 'node:path';

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
page.on('dialog', dialog => dialog.accept());

const evidence = { network: [], console: [], pageErrors: [], steps: {} };
page.on('console', message => evidence.console.push({ type: message.type(), text: message.text() }));
page.on('pageerror', error => evidence.pageErrors.push(error.message));
page.on('response', async response => {
  if (!response.url().includes('localhost:8001/api/') || response.url().endsWith('/auth/login')) return;
  let body = '';
  try { body = (await response.text()).slice(0, 4000); } catch {}
  evidence.network.push({ method: response.request().method(), url: response.url(), status: response.status(), body });
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
async function buttonExists(text) {
  return page.$$eval('button', (buttons, expected) => buttons.some(item => item.innerText.trim() === expected), text);
}
async function fillPlaceholder(placeholder, value) {
  const input = await page.$(`input[placeholder="${placeholder}"],textarea[placeholder="${placeholder}"]`);
  if (!input) throw new Error(`Input not found: ${placeholder}`);
  await input.focus();
  await page.keyboard.down('Control');
  await page.keyboard.press('KeyA');
  await page.keyboard.up('Control');
  await page.keyboard.press('Backspace');
  await input.type(value);
}
async function state() {
  return page.evaluate(() => ({
    bodyText: document.body.innerText.slice(0, 18000),
    controls: [...document.querySelectorAll('button,input,textarea,select')].map(el => ({
      tag: el.tagName,
      text: el.innerText?.trim(),
      type: el.getAttribute('type'),
      placeholder: el.getAttribute('placeholder'),
      value: el.type === 'password' ? '[redacted]' : el.value,
      disabled: Boolean(el.disabled),
    })),
  }));
}

await page.goto('http://localhost:5174', { waitUntil: 'networkidle2', timeout: 30000 });
const loginInputs = await page.$$('input');
await loginInputs[0].focus();
await page.keyboard.down('Control');
await page.keyboard.press('KeyA');
await page.keyboard.up('Control');
await page.keyboard.press('Backspace');
await loginInputs[0].type('cietadmin');
await loginInputs[1].type('CIET-QA-2026!Strong');
await clickButton('Sign in');
await delay(1200);

await clickButton('FAQs');
await delay(700);
if (await buttonExists('Delete')) {
  await clickButton('Delete');
  await delay(700);
}
await fillPlaceholder('Verified question', 'What is the CIET black-box QA verification code?');
await fillPlaceholder('Verified answer', 'The controlled verification code is CYGNUS-7429.');
await clickButton('Add FAQ');
await delay(900);
evidence.steps.faqCreated = await state();
await page.screenshot({ path: new URL('./faq-created.png', screenshots).pathname, fullPage: true });

evidence.steps.faqEditAvailable = await buttonExists('Edit');
if (evidence.steps.faqEditAvailable) {
  await clickButton('Edit');
  await delay(400);
  evidence.steps.faqEditMode = await state();
  const answerInput = await page.$('input[value="The controlled verification code is CYGNUS-7429."]');
  if (answerInput) {
    await answerInput.focus();
    await page.keyboard.down('Control');
    await page.keyboard.press('KeyA');
    await page.keyboard.up('Control');
    await answerInput.type('The edited controlled verification code is CYGNUS-7429.');
  }
  await clickButton('Save');
  await delay(800);
  evidence.steps.faqEdited = await state();
  await page.screenshot({ path: new URL('./faq-edited.png', screenshots).pathname, fullPage: true });
}
await clickButton('Delete');
await delay(800);
evidence.steps.faqDeleted = await state();

await clickButton('Metrics');
await delay(700);
await fillPlaceholder('Metric name', 'QA Applications');
await fillPlaceholder('Verified value', '742');
await clickButton('Add Metric');
await delay(800);
evidence.steps.metricCreated = await state();
await page.screenshot({ path: new URL('./metric-created.png', screenshots).pathname, fullPage: true });
await clickButton('Delete');
await delay(800);
evidence.steps.metricDeleted = await state();

await clickButton('Documents');
await delay(700);
const fileInput = await page.$('input[type="file"]');
const fixture = path.resolve('qa_evidence/fixtures/CIET_QA_RAG.txt');
await fileInput.uploadFile(fixture);
await delay(3500);
evidence.steps.documentUploaded = await state();
await page.screenshot({ path: new URL('./document-uploaded.png', screenshots).pathname, fullPage: true });

for (let attempt = 0; attempt < 12; attempt += 1) {
  const text = await page.evaluate(() => document.body.innerText);
  if (/completed|indexed|failed/i.test(text)) break;
  await delay(5000);
  await clickButton('Refresh Knowledge');
  await delay(500);
}
evidence.steps.documentFinal = await state();
await page.screenshot({ path: new URL('./document-final.png', screenshots).pathname, fullPage: true });

await browser.close();
await fs.writeFile(new URL('./admin-crud-upload-report.json', base), JSON.stringify(evidence, null, 2));
console.log(JSON.stringify(evidence, null, 2));
