import {createRequire} from 'node:module';
import {mkdir, writeFile} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import {resolve} from 'node:path';

const require = createRequire(resolve('tests/package.json'));
const {chromium} = require('playwright-core');
const AxeBuilder = require('@axe-core/playwright').default;
const base = process.env.BASE_URL || 'http://127.0.0.1:8772/';
const output = resolve(process.env.ZHIWEI_GATE_QA_DIR || 'artifacts/qa/zhiwei-gate');
await mkdir(output, {recursive: true});
const chrome = process.env.CHROMIUM_PATH || '/usr/bin/google-chrome';
const browser = await chromium.launch({headless: true, executablePath: existsSync(chrome) ? chrome : undefined, args: ['--no-sandbox']});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'no-preference'});
const page = await context.newPage();
page.setDefaultTimeout(12000);
const results = [], errors = [], missing = [];
function observe(current) {
  current.on('pageerror', error => errors.push(error.message));
  current.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  current.on('response', response => { if (response.status() >= 400) missing.push({url: response.url(), status: response.status()}); });
}
observe(page);
function assert(value, message) { if (!value) throw new Error(message); }
async function test(name, action) {
  try { results.push({name, pass: true, detail: await action()}); }
  catch (error) { results.push({name, pass: false, error: error.message}); console.error('FAIL', name, error.message); }
}
async function gateReady(current = page) {
  await current.locator('#gateway[data-phase="idle"]:visible').waitFor();
  await current.evaluate(() => document.fonts.ready);
}
async function returnToGate() {
  await page.locator('.brand').click();
  await gateReady();
  assert(new URL(page.url()).hash === '#gateway', 'Brand did not restore the entrance route');
}
async function atSection(hash, current = page) {
  await current.locator('#gateway').waitFor({state: 'hidden'});
  await current.waitForFunction(hash => {
    const target = document.querySelector(hash);
    const rect = target.getBoundingClientRect();
    return !document.querySelector('#main').inert && rect.top < 100 && rect.bottom > innerHeight / 2;
  }, hash);
  assert(new URL(current.url()).hash === hash, 'Selected section was not kept in the URL');
  await current.waitForFunction(() => !document.querySelector('.zw-gate-flight'));
}
try {
  await test('intro can be skipped and replayed without duplicating the scene', async () => {
    await page.goto(base, {waitUntil: 'domcontentloaded'});
    await page.locator('.zw-gate-skip:visible').click();
    await gateReady();
    assert(await page.locator('.zw-orb-link').count() === 5, 'Entrance does not have five paths');
    await page.locator('.zw-gate-replay').click();
    await page.locator('#gateway[data-phase="intro"]').waitFor();
    await page.keyboard.press('Escape');
    await gateReady();
    assert(await page.locator('#gateway').count() === 1 && await page.locator('.zw-gate-optics').count() === 1, 'Replay duplicated the scene');
    assert(await page.locator('.zw-orb-link').first().evaluate(link => link === document.activeElement), 'Skip did not focus a usable path');
  });
  await test('every orb reaches its matching section and supports returning', async () => {
    for (let index = 1; index <= 5; index++) {
      await page.locator(`.zw-orb-link[href="#s${index}"]`).click();
      await atSection(`#s${index}`);
      await page.locator('#specimen-stage svg').waitFor();
      await returnToGate();
    }
    return {destinations: ['s1', 's2', 's3', 's4', 's5']};
  });
  await test('keyboard arrows, Enter, Escape and top navigation remain usable', async () => {
    await page.locator('.zw-orb-link').first().focus();
    await page.keyboard.press('ArrowRight');
    assert(await page.locator('.zw-orb-link').nth(1).evaluate(link => link === document.activeElement), 'Arrow navigation did not move focus');
    await page.keyboard.press('End');
    await page.keyboard.press('Enter');
    await atSection('#s5');
    await returnToGate();
    await page.keyboard.press('Escape');
    await atSection('#s5');
    await returnToGate();
    await page.locator('.deck-nav a[href="#s3"]').click();
    await atSection('#s3');
  });
  await test('scrolling between the original five sections still works', async () => {
    await page.evaluate(() => document.querySelector('#s4').scrollIntoView({behavior: 'instant'}));
    await page.waitForFunction(() => document.querySelector('.deck-nav a.is-active')?.hash === '#s4');
    await page.locator('#tab-c').click();
    assert(await page.locator('#tab-c').getAttribute('aria-selected') === 'true', 'Findings pager stopped working');
    await page.evaluate(() => document.querySelector('#s5').scrollIntoView({behavior: 'instant'}));
    await page.waitForFunction(() => document.querySelector('.deck-nav a.is-active')?.hash === '#s5');
  });
  await test('browser Back and Forward restore entrance and content', async () => {
    await returnToGate();
    await page.locator('.zw-orb-link[href="#s2"]').click();
    await atSection('#s2');
    await page.goBack();
    await gateReady();
    await page.goForward();
    await atSection('#s2');
  });
  await test('section deep links and chapter URLs bypass the opening', async () => {
    for (const route of ['#s4', '?chapter=cleaning', '?chapter=findings&topic=feedback']) {
      await page.goto(new URL(route, base).href, {waitUntil: 'networkidle'});
      await page.locator('#specimen-stage svg').waitFor();
      assert(await page.locator('#gateway').isHidden(), 'Opening blocked a deep link: ' + route);
      assert(!await page.locator('#main').evaluate(main => main.inert), 'Deep-linked content remained inert');
    }
    assert(await page.locator('#tab-c').getAttribute('aria-selected') === 'true', 'Feedback chapter did not keep its findings page');
    await page.reload({waitUntil: 'networkidle'});
    assert(await page.locator('#gateway').isHidden(), 'Refresh reopened the entrance over a section');
  });
  await test('desktop, tablet, phone and short landscape keep all five paths reachable', async () => {
    const sizes = [[1440, 900], [1024, 768], [390, 844], [320, 568], [844, 390]];
    for (const [width, height] of sizes) {
      await page.setViewportSize({width, height});
      await returnToGate();
      await page.locator('.zw-gate-start').scrollIntoViewIfNeeded();
      await page.locator('.zw-gate-optics').evaluate(optics => { for (const animation of optics.getAnimations()) animation.currentTime = 12500; });
      assert(await page.locator('#gateway').evaluate(gate => gate.scrollWidth <= gate.clientWidth + 1), `Entrance overflows horizontally at ${width}×${height}`);
      for (const link of await page.locator('.zw-orb-link').all()) {
        await link.scrollIntoViewIfNeeded();
        await link.click({trial: true});
      }
      await page.locator('#gateway').evaluate(gate => { gate.scrollTop = 0; });
      await page.screenshot({path: resolve(output, `entrance-${width}x${height}.png`)});
    }
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('.zw-orb-link[href="#s4"]').click();
    await atSection('#s4');
  });
  await test('reduced motion gives an immediate entrance and immediate navigation', async () => {
    const reduced = await browser.newContext({viewport: {width: 390, height: 844}, reducedMotion: 'reduce', hasTouch: true});
    try {
      const current = await reduced.newPage(); observe(current);
      await current.goto(base, {waitUntil: 'networkidle'});
      await gateReady(current);
      assert(await current.locator('.zw-gate-skip').isHidden(), 'Reduced motion still played the intro');
      assert(await current.locator('.zw-gate-replay').isHidden(), 'Reduced motion exposed an animation-only control');
      await current.locator('.zw-orb-link[href="#s3"]').tap();
      await atSection('#s3', current);
    } finally { await reduced.close(); }
  });
  await test('changing motion preference during a transition completes the chosen path', async () => {
    await page.setViewportSize({width: 1440, height: 900});
    await returnToGate();
    await page.locator('.zw-orb-link[href="#s5"]').click();
    await page.emulateMedia({reducedMotion: 'reduce'});
    await atSection('#s5');
    await page.emulateMedia({reducedMotion: 'no-preference'});
  });
  await test('entrance has no serious or critical accessibility findings', async () => {
    await returnToGate();
    const report = await new AxeBuilder({page}).analyze();
    const blockers = report.violations.filter(item => ['serious', 'critical'].includes(item.impact));
    await writeFile(resolve(output, 'accessibility.json'), JSON.stringify(report.violations, null, 2));
    assert(blockers.length === 0, blockers.map(item => item.id + ': ' + item.nodes.map(node => node.target.join(' ')).join(', ')).join('; '));
    return {violations: report.violations.length};
  });
  await test('a complete opening settles automatically with all controls enabled', async () => {
    await page.locator('.zw-gate-replay').click();
    await gateReady();
    assert(!await page.locator('.zw-gate-orbits').evaluate(nav => nav.inert), 'Paths stayed inert after the intro');
    await page.locator('.zw-gate-start').click();
    await atSection('#s1');
  });
} finally {
  results.push({name: 'no JavaScript errors or missing resources', pass: errors.length === 0 && missing.length === 0, detail: {errors, missing}});
  await writeFile(resolve(output, 'results.json'), JSON.stringify(results, null, 2));
  await browser.close();
}
const failed = results.filter(result => !result.pass);
console.log(JSON.stringify({passed: results.length - failed.length, failed: failed.length, output}));
if (failed.length) process.exitCode = 1;
