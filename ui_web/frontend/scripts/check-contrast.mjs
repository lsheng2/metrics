// WCAG contrast gate for the generated Meridian theme tokens (light and dark).
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { converter, wcagContrast } from 'culori';

import { frontendDir, staticDir } from './shared.mjs';

const toRgb = converter('rgb');
const THEME_SELECTORS = {
  light: ':root,\n[data-theme="light"]',
  dark: '[data-theme="dark"]',
};

function themeVariables(css, selector) {
  const start = css.indexOf(`${selector} {`);
  if (start < 0) {
    throw new Error(`Theme block not found: ${selector}`);
  }
  const body = css.slice(start, css.indexOf('\n}', start));
  const variables = new Map();
  for (const match of body.matchAll(/--([a-z0-9-]+):\s*([^;]+);/g)) {
    variables.set(match[1], match[2].trim());
  }
  return variables;
}

function opaque(foreground, background) {
  const fg = toRgb(foreground);
  const bg = toRgb(background);
  const alpha = fg.alpha ?? 1;
  if (alpha >= 1) {
    return fg;
  }
  return {
    mode: 'rgb',
    r: fg.r * alpha + bg.r * (1 - alpha),
    g: fg.g * alpha + bg.g * (1 - alpha),
    b: fg.b * alpha + bg.b * (1 - alpha),
  };
}

const css = readFileSync(path.join(staticDir, 'css', 'theme.css'), 'utf8').replace(/\r\n/g, '\n');
const { pairs } = JSON.parse(readFileSync(path.join(frontendDir, 'tokens', 'contrast-pairs.json'), 'utf8'));
const failures = [];
const warnings = [];
let checked = 0;

const baseVariables = themeVariables(css, ':root');

for (const [theme, selector] of Object.entries(THEME_SELECTORS)) {
  const variables = new Map([...baseVariables, ...themeVariables(css, selector)]);
  for (const pair of pairs) {
    for (const backgroundName of pair.bg) {
      const foreground = variables.get(pair.fg);
      const background = variables.get(backgroundName);
      if (!foreground || !background) {
        failures.push(`${theme}: unknown token in pair ${pair.fg} on ${backgroundName}`);
        continue;
      }
      checked += 1;
      const ratio = wcagContrast(opaque(foreground, background), background);
      if (ratio + 1e-9 < pair.min) {
        const line = `${theme}: --${pair.fg} (${foreground}) on --${backgroundName} (${background}) = ${ratio.toFixed(2)} < ${pair.min}`;
        (pair.level === 'error' ? failures : warnings).push(line);
      }
    }
  }
}

for (const line of warnings) {
  console.warn(`warn  ${line}`);
}
for (const line of failures) {
  console.error(`FAIL  ${line}`);
}
console.log(`Contrast pairs checked: ${checked}; failures: ${failures.length}; warnings: ${warnings.length}.`);
if (failures.length) {
  process.exit(1);
}
