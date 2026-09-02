import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';

const base = new URL('./', import.meta.url);
const browser = await puppeteer.launch({ headless: true, executablePath: '/usr/bin/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage();
const report = { responses: {}, maliciousOriginCors: {} };
for (const [name, url] of [
  ['health', 'http://localhost:8001/healthz'],
  ['docs', 'http://localhost:8001/docs'],
  ['metrics', 'http://localhost:8001/metrics'],
  ['widget', 'http://localhost:5173'],
  ['admin', 'http://localhost:5174'],
]) {
  const response = await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
  report.responses[name] = { status: response.status(), headers: response.headers() };
}

const evil = await browser.newPage();
await evil.setRequestInterception(true);
evil.on('request', request => {
  if (request.url() === 'http://evil.test/') {
    request.respond({ status: 200, contentType: 'text/html', body: '<!doctype html><title>Evil origin test</title>' });
  } else {
    request.continue();
  }
});
const apiResponses = [];
evil.on('response', response => {
  if (response.url().includes('localhost:8001')) apiResponses.push({ url: response.url(), status: response.status(), headers: response.headers() });
});
await evil.goto('http://evil.test/', { waitUntil: 'domcontentloaded', timeout: 30000 });
report.maliciousOriginCors.origin = await evil.evaluate(() => location.origin);
report.maliciousOriginCors.fetchResult = await evil.evaluate(async () => {
  try {
    const response = await fetch('http://localhost:8001/healthz');
    return { readable: true, status: response.status, body: await response.text() };
  } catch (error) {
    return { readable: false, error: String(error) };
  }
});
report.maliciousOriginCors.apiResponses = apiResponses;

await browser.close();
await fs.writeFile(new URL('./security-headers-cors-report.json', base), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
