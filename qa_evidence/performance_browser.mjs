import puppeteer from 'puppeteer';
import fs from 'node:fs/promises';
import { execFileSync } from 'node:child_process';

const base = new URL('./', import.meta.url);
const browser = await puppeteer.launch({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const tabCount = 10;
function processSnapshot() {
  const rows = execFileSync('ps', ['-eo', 'comm,%cpu,rss,args'], { encoding: 'utf8' }).trim().split('\n').slice(1);
  const groups = { chromium: { processes: 0, cpuPercent: 0, rssKiB: 0 }, uvicorn: { processes: 0, cpuPercent: 0, rssKiB: 0 }, celery: { processes: 0, cpuPercent: 0, rssKiB: 0 }, vite: { processes: 0, cpuPercent: 0, rssKiB: 0 } };
  for (const row of rows) {
    const match = row.trim().match(/^(\S+)\s+([0-9.]+)\s+(\d+)\s+(.*)$/);
    if (!match) continue;
    const [, comm, cpu, rss, args] = match;
    let group;
    if (/chromium|chrome/i.test(`${comm} ${args}`)) group = 'chromium';
    else if (/uvicorn/.test(args)) group = 'uvicorn';
    else if (/celery/.test(args)) group = 'celery';
    else if (/node_modules\/\.bin\/vite/.test(args)) group = 'vite';
    if (!group) continue;
    groups[group].processes += 1;
    groups[group].cpuPercent += Number(cpu);
    groups[group].rssKiB += Number(rss);
  }
  for (const group of Object.values(groups)) group.rssMiB = Math.round(group.rssKiB / 1024 * 10) / 10;
  return groups;
}
const pages = await Promise.all(Array.from({ length: tabCount }, async () => {
  const page = await browser.newPage();
  await page.setViewport({ width: 414, height: 800 });
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle2', timeout: 30000 });
  await page.click('button[aria-label="Open CIET AI Assistant"]');
  return page;
}));
console.error(`TABS_READY ${tabCount}`);
const resourcesWithTabs = processSnapshot();

const results = await Promise.all(pages.map(async (page, index) => {
  const query = `Concurrent browser test ${index + 1}: What courses are available?`;
  const textarea = await page.$('textarea');
  await textarea.type(query);
  const started = performance.now();
  const responsePromise = page.waitForResponse(response =>
    response.request().method() === 'POST' && response.url().includes('localhost:8001/api/'),
    { timeout: 30000 },
  );
  await page.click('button[type="submit"]');
  try {
    const response = await responsePromise;
    const body = await response.text();
    return { index, status: response.status(), latencyMs: Math.round(performance.now() - started), body: body.slice(0, 1200) };
  } catch (error) {
    return { index, timeout: true, latencyMs: Math.round(performance.now() - started), error: error.message };
  }
}));

const latencies = results.filter(item => !item.timeout).map(item => item.latencyMs).sort((a, b) => a - b);
const percentile = value => latencies[Math.min(latencies.length - 1, Math.ceil(latencies.length * value) - 1)];
const report = {
  tabCount,
  results,
  resourcesWithTabs,
  resourcesAfterRequests: processSnapshot(),
  summary: {
    success2xx: results.filter(item => item.status >= 200 && item.status < 300).length,
    rateLimited429: results.filter(item => item.status === 429).length,
    timeouts: results.filter(item => item.timeout).length,
    minMs: latencies[0],
    p50Ms: percentile(0.5),
    p95Ms: percentile(0.95),
    maxMs: latencies.at(-1),
  },
};
await fs.writeFile(new URL('./performance-browser-report.json', base), JSON.stringify(report, null, 2));
console.error(`REQUESTS_DONE ${JSON.stringify(report.summary)}`);
await new Promise(resolve => setTimeout(resolve, 1000));
await browser.close();
console.log(JSON.stringify(report, null, 2));
