// Builds ui_web/static/css/theme.css from DTCG token files with Style Dictionary.
// Primitive ramps come from @radix-ui/colors and are referenced as {ramp.<scale>.<step>};
// they are resolved at build time and never emitted as CSS variables.
import { readFileSync } from 'node:fs';
import path from 'node:path';

import * as radix from '@radix-ui/colors';
import StyleDictionary from 'style-dictionary';

import { finishDriftCheck, frontendDir, staticDir, writeOrCheck } from './shared.mjs';

const RAMP_SCALES = ['slate', 'indigo', 'grass', 'amber', 'red', 'blue', 'orange', 'teal', 'crimson', 'cyan', 'violet'];
const ALPHA_SCALES = ['blackA', 'whiteA'];
const STEPS = Array.from({ length: 12 }, (_, index) => index + 1);
const OUTPUT_FILE = path.join(staticDir, 'css', 'theme.css');

function readTokens(fileName) {
  return JSON.parse(readFileSync(path.join(frontendDir, 'tokens', fileName), 'utf8'));
}

function rampTokens(theme) {
  const ramp = {};
  for (const scale of RAMP_SCALES) {
    const source = radix[theme === 'dark' ? `${scale}Dark` : scale];
    ramp[scale] = Object.fromEntries(
      STEPS.map((step) => [step, { $type: 'color', $value: source[`${scale}${step}`] }]),
    );
  }
  for (const scale of ALPHA_SCALES) {
    ramp[scale] = Object.fromEntries(
      STEPS.map((step) => [step, { $type: 'color', $value: radix[scale][`${scale}${step}`] }]),
    );
  }
  return { ramp };
}

function colorTokenPaths(group, inheritedType, prefix = []) {
  const groupType = group.$type ?? inheritedType;
  const paths = [];
  for (const [key, value] of Object.entries(group)) {
    if (key.startsWith('$') || value === null || typeof value !== 'object') {
      continue;
    }
    const tokenPath = [...prefix, key];
    if ('$value' in value) {
      if ((value.$type ?? groupType) === 'color') {
        paths.push(tokenPath.join('.'));
      }
    } else {
      paths.push(...colorTokenPaths(value, groupType, tokenPath));
    }
  }
  return paths;
}

function assertColorParity(lightTokens, darkTokens) {
  const light = new Set(colorTokenPaths(lightTokens));
  const dark = new Set(colorTokenPaths(darkTokens));
  const problems = [
    ...[...light].filter((name) => !dark.has(name)).map((name) => `dark theme is missing ${name}`),
    ...[...dark].filter((name) => !light.has(name)).map((name) => `light theme is missing ${name}`),
  ];
  if (problems.length) {
    console.error(`Every color token needs a light and a dark value (${problems.length}):`);
    for (const line of problems) {
      console.error(`  - ${line}`);
    }
    process.exit(1);
  }
}

function declaration(token) {
  const description = token.$description ? ` /* ${token.$description} */` : '';
  return `  --${token.name}: ${token.$value};${description}`;
}

async function formatDeclarations(tokens) {
  const dictionary = new StyleDictionary({
    tokens,
    usesDtcg: true,
    log: { verbosity: 'silent', warnings: 'disabled' },
    hooks: {
      formats: {
        'meridian/declarations': ({ dictionary: formatted }) =>
          formatted.allTokens.map(declaration).join('\n'),
      },
    },
    platforms: {
      css: {
        transforms: ['name/kebab', 'fontFamily/css', 'cubicBezier/css', 'shadow/css/shorthand'],
        files: [
          {
            destination: 'theme.css',
            format: 'meridian/declarations',
            filter: (token) => token.path[0] !== 'ramp',
          },
        ],
      },
    },
  });
  const [file] = await dictionary.formatPlatform('css');
  return file.output;
}

function block(selector, body, colorScheme) {
  const scheme = colorScheme ? `  color-scheme: ${colorScheme};\n` : '';
  return `${selector} {\n${scheme}${body}\n}\n`;
}

const lightTokens = readTokens('theme.light.tokens.json');
const darkTokens = readTokens('theme.dark.tokens.json');
assertColorParity(lightTokens, darkTokens);

const base = await formatDeclarations(readTokens('base.tokens.json'));
const light = await formatDeclarations({ ...rampTokens('light'), ...lightTokens });
const dark = await formatDeclarations({ ...rampTokens('dark'), ...darkTokens });

const css = [
  '/*\n'
    + ' * Meridian design tokens. GENERATED FILE - DO NOT EDIT.\n'
    + ' * Source: ui_web/frontend/tokens/*.tokens.json + @radix-ui/colors ramps.\n'
    + ' * Rebuild: cd ui_web/frontend && npm run build:tokens\n'
    + ' */\n',
  block(':root', base),
  block(':root,\n[data-theme="light"]', light, 'light'),
  block('[data-theme="dark"]', dark, 'dark'),
].join('\n');

const drift = [];
writeOrCheck(OUTPUT_FILE, css, drift);
finishDriftCheck(drift, 'npm run build:tokens');
if (!process.argv.includes('--check')) {
  console.log(`Wrote ${path.relative(process.cwd(), OUTPUT_FILE)}`);
}
