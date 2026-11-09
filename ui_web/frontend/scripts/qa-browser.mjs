// Browser QA gate: renders dashboard routes in every theme and viewport, then fails on server
// errors, page-level horizontal overflow, console errors, failed same-origin requests and
// serious/critical axe-core accessibility violations. The run is hermetic: cross-origin requests
// are blocked, an external script/stylesheet/font fails the check (runtime assets are vendored,
// never loaded from a CDN) and other blocked requests (Grafana embeds, provider avatars) are
// warnings. Screenshots and report.json go to .qa/browser, which every run recreates.
import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import path from 'node:path';

import AxeBuilderModule from '@axe-core/playwright';
import { chromium } from 'playwright-core';

import { frontendDir } from './shared.mjs';

const AxeBuilder = AxeBuilderModule.default ?? AxeBuilderModule;
const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const BLOCKING_IMPACTS = new Set(['serious', 'critical']);
const VENDORED_RESOURCE_TYPES = new Set(['script', 'stylesheet', 'font']);
const OUT_DIR = path.join(frontendDir, '.qa', 'browser');

function listEnv(name, fallback) {
  const raw = process.env[name];
  if (!raw) {
    return fallback;
  }
  return raw.split(',').map((item) => item.trim()).filter(Boolean);
}

function parseViewport(value) {
  const match = /^(\d+)x(\d+)$/.exec(value);
  if (!match) {
    throw new Error(`Invalid viewport "${value}", expected WIDTHxHEIGHT`);
  }
  return { width: Number(match[1]), height: Number(match[2]) };
}

const baseUrl = process.env.DASHBOARD_QA_BASE_URL;
if (!baseUrl) {
  console.error('Set DASHBOARD_QA_BASE_URL to the dashboard under test, for example http://127.0.0.1:8793');
  process.exit(2);
}
const origin = new URL(baseUrl).origin;
const basicAuth = process.env.DASHBOARD_QA_BASIC_AUTH ?? '';
const separator = basicAuth.indexOf(':');
const httpCredentials = separator > 0
  ? { username: basicAuth.slice(0, separator), password: basicAuth.slice(separator + 1) }
  : undefined;
const themes = listEnv('DASHBOARD_QA_THEMES', ['light', 'dark']);
const viewports = listEnv('DASHBOARD_QA_VIEWPORTS', ['1440x900', '390x844']).map(parseViewport);
const skipRoutes = new Set(listEnv('DASHBOARD_QA_SKIP_ROUTES', []));
const concurrency = Math.max(1, Number(process.env.DASHBOARD_QA_CONCURRENCY ?? 3));
const fullPage = process.env.DASHBOARD_QA_FULL_PAGE === '1';

function sameOriginPath(url) {
  const parsed = new URL(url, origin);
  return parsed.origin === origin ? `${parsed.pathname}${parsed.search}` : null;
}

function slug(route) {
  return route.replace(/^\/+|\/+$/g, '').replace(/[^a-z0-9]+/gi, '-').toLowerCase() || 'home';
}

function newContext(browser, theme, viewport) {
  return browser.newContext({
    viewport,
    colorScheme: theme === 'dark' ? 'dark' : 'light',
    reducedMotion: 'reduce',
    httpCredentials,
  });
}

async function discoverRoutes(browser) {
  const configured = listEnv('DASHBOARD_QA_ROUTES', null);
  if (configured) {
    return configured;
  }
  const context = await newContext(browser, 'light', viewports[0]);
  try {
    const page = await context.newPage();
    await page.goto(new URL('/', origin).href, { waitUntil: 'domcontentloaded', timeout: 60_000 });
    const hrefs = await page.$$eval('.app-nav__link[href]', (links) => links.map((link) => link.getAttribute('href')));
    return [...new Set(['/', ...hrefs.map(sameOriginPath).filter(Boolean)])];
  } finally {
    await context.close();
  }
}

async function settle(page) {
  await page.waitForLoadState('networkidle', { timeout: 15_000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready.then(() => true));
  await page.waitForTimeout(250);
}

async function audit(browser, check) {
  const { route, theme, viewport } = check;
  const context = await newContext(browser, theme, viewport);
  await context.addInitScript((value) => {
    try {
      window.localStorage.setItem('dashboard-theme', value);
    } catch {
      // Storage can be unavailable on opaque origins; the colorScheme emulation still applies.
    }
  }, theme);
  const page = await context.newPage();
  const consoleErrors = [];
  const failedRequests = [];
  const externalRequests = [];
  await context.route((url) => url.origin !== origin, (route) => {
    const request = route.request();
    externalRequests.push({ type: request.resourceType(), url: request.url().slice(0, 160) });
    return route.abort('blockedbyclient');
  });
  page.on('console', (message) => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource')) {
      consoleErrors.push(message.text());
    }
  });
  page.on('pageerror', (error) => consoleErrors.push(String(error)));
  page.on('response', (response) => {
    const request = response.request();
    const target = sameOriginPath(response.url());
    if (response.status() >= 400 && target && !(request.isNavigationRequest() && request.frame() === page.mainFrame())) {
      failedRequests.push(`${response.status()} ${target}`);
    }
  });
  // Same-origin requests that never got a response (refused, reset, DNS); ERR_ABORTED is a request
  // superseded by navigation or an htmx swap, not a broken asset.
  page.on('requestfailed', (request) => {
    const target = sameOriginPath(request.url());
    const reason = request.failure()?.errorText ?? 'unknown failure';
    if (target && reason !== 'net::ERR_ABORTED') {
      failedRequests.push(`${reason} ${target}`);
    }
  });
  const result = { ...check, viewport: `${viewport.width}x${viewport.height}`, problems: [], warnings: [] };
  try {
    const response = await page.goto(new URL(route, origin).href, { waitUntil: 'load', timeout: 60_000 });
    result.status = response ? response.status() : 0;
    await settle(page);
    const layout = await page.evaluate(() => ({
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      appliedTheme: document.documentElement.getAttribute('data-theme'),
    }));
    Object.assign(result, layout);
    const axe = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze();
    result.violations = axe.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      help: violation.help,
      nodes: violation.nodes.length,
      targets: violation.nodes.slice(0, 3).map((node) => node.target.join(' ')),
      details: violation.nodes.slice(0, 25).map((node) => {
        const data = node.any?.[0]?.data ?? {};
        return {
          target: node.target.join(' '),
          ...(violation.id === 'color-contrast'
            ? { fg: data.fgColor, bg: data.bgColor, ratio: data.contrastRatio, expected: data.expectedContrastRatio, fontSize: data.fontSize }
            : { summary: node.failureSummary?.split('\n').slice(1, 3).join(' ').trim() }),
        };
      }),
    }));
    const file = `${slug(route)}-${theme}-${result.viewport}.png`;
    await page.screenshot({ path: path.join(OUT_DIR, file), fullPage });
    result.screenshot = file;
  } catch (error) {
    result.problems.push(`navigation failed: ${error.message.split('\n')[0]}`);
  } finally {
    await context.close();
  }
  if (result.status >= 400) {
    result.problems.push(`HTTP ${result.status}`);
  }
  if (result.overflowX > 1) {
    result.problems.push(`page overflows horizontally by ${result.overflowX}px`);
  }
  if (result.appliedTheme && result.appliedTheme !== theme) {
    result.problems.push(`theme "${theme}" requested but "${result.appliedTheme}" applied`);
  }
  for (const text of consoleErrors) {
    result.problems.push(`console: ${text.slice(0, 160)}`);
  }
  for (const text of [...new Set(failedRequests)]) {
    result.problems.push(`request: ${text}`);
  }
  for (const text of new Set(externalRequests.map(({ type, url }) => `${type} ${url}`))) {
    const type = text.slice(0, text.indexOf(' '));
    (VENDORED_RESOURCE_TYPES.has(type) ? result.problems : result.warnings).push(`external ${text} (blocked)`);
  }
  for (const violation of result.violations ?? []) {
    const line = `axe ${violation.id} (${violation.impact}) x${violation.nodes}: ${violation.targets.join(' | ')}`;
    (BLOCKING_IMPACTS.has(violation.impact) ? result.problems : result.warnings).push(line);
  }
  return result;
}

async function main() {
  rmSync(OUT_DIR, { recursive: true, force: true });
  mkdirSync(OUT_DIR, { recursive: true });
  const browser = await chromium.launch({
    channel: process.env.DASHBOARD_QA_BROWSER_PATH ? undefined : (process.env.DASHBOARD_QA_BROWSER_CHANNEL ?? 'msedge'),
    executablePath: process.env.DASHBOARD_QA_BROWSER_PATH || undefined,
    headless: true,
  });
  try {
    const routes = (await discoverRoutes(browser)).filter((route) => !skipRoutes.has(route));
    const queue = routes.flatMap((route) => themes.flatMap((theme) => viewports.map((viewport) => ({ route, theme, viewport }))));
    const results = [];
    const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
      for (let check = queue.shift(); check; check = queue.shift()) {
        const result = await audit(browser, check);
        results.push(result);
        const label = `${result.route} ${result.theme} ${result.viewport}`;
        console.log(`${result.problems.length ? 'FAIL' : 'PASS'}  ${label}${result.warnings.length ? `  (${result.warnings.length} warnings)` : ''}`);
        for (const problem of result.problems) {
          console.log(`      - ${problem}`);
        }
      }
    });
    await Promise.all(workers);
    results.sort((a, b) => `${a.route}${a.theme}${a.viewport}`.localeCompare(`${b.route}${b.theme}${b.viewport}`));
    const failed = results.filter((result) => result.problems.length);
    const summary = { baseUrl: origin, routes, themes, checks: results.length, failed: failed.length };
    writeFileSync(path.join(OUT_DIR, 'report.json'), `${JSON.stringify({ summary, results }, null, 2)}\n`);
    console.log(`Browser QA: ${results.length} checks, ${failed.length} failed. Report: ui_web/frontend/.qa/browser/report.json`);
    process.exitCode = failed.length ? 1 : 0;
  } finally {
    await browser.close();
  }
}

await main();
