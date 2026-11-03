// Optional developer QA: node scripts/visual_check.cjs <demo-dir> <output-dir>
// Install Playwright separately, or set PATCHREPLAY_PLAYWRIGHT_MODULE to its path.
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL, fileURLToPath} = require('node:url');
const {chromium} = require(process.env.PATCHREPLAY_PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const root = path.resolve(process.argv[2]);
  const output = path.resolve(process.argv[3]);
  fs.mkdirSync(output, {recursive: true});
  const summary = JSON.parse(fs.readFileSync(path.join(root, 'suite-results.json'), 'utf8'));
  const launch = {headless: true};
  if (process.env.PATCHREPLAY_BROWSER) launch.executablePath = process.env.PATCHREPLAY_BROWSER;
  const browser = await chromium.launch(launch);
  const results = [];
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({viewport: {width, height: 1000}});
      const failures = [];
      page.on('pageerror', error => failures.push(error.message));
      page.on('request', request => {
        if (/^https?:/.test(request.url())) failures.push('Unexpected remote request: ' + request.url());
      });
      for (const name of ['index', 'good', 'regression', 'protected']) {
        const file = name === 'index' ? path.join(root, 'index.html') : path.join(root, summary.cases.find(c => c.case_id === name).package, 'report.html');
        await page.goto(pathToFileURL(file).href);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
        if (overflow) failures.push('Document overflow: ' + name);
        const links = await page.locator('a').evaluateAll(nodes => nodes.map(node => node.href));
        for (const href of links) {
          if (href.startsWith('file:') && !fs.existsSync(fileURLToPath(href))) failures.push('Missing local link: ' + href);
        }
        const details = page.locator('details');
        if (await details.count()) {
          await details.first().locator('summary').click();
          if (!await details.first().getAttribute('open') && await details.first().getAttribute('open') !== '') failures.push('Details failed to open');
          await details.first().locator('summary').click();
        }
        await page.screenshot({path: path.join(output, `${name}-${width}.png`), fullPage: true});
        results.push({page: name, viewport: width, title: await page.title(), overflow, links: links.length});
      }
      await page.close();
      if (failures.length) throw new Error(failures.join('\n'));
    }
    fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify({passed: true, results}, null, 2));
    console.log(JSON.stringify({passed: true, checks: results.length, output}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
