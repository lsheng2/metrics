// Copies pinned third-party runtime assets from node_modules into ui_web/static/vendor,
// generates the iconoir subset and font-face CSS, and records a hash manifest.
// Django serves only the vendored copies; templates must never load assets from a CDN.
import { readdirSync, readFileSync, rmSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';

import {
  finishDriftCheck,
  frontendDir,
  isCheckMode,
  nodeModulesDir,
  normalizeNewlines,
  repoRelative,
  repoRoot,
  sha256,
  staticDir,
  uiWebDir,
  writeOrCheck,
} from './shared.mjs';

const VENDOR_DIR = path.join(staticDir, 'vendor');
const packageJson = JSON.parse(readFileSync(path.join(frontendDir, 'package.json'), 'utf8'));
const drift = [];
const files = {};

function packageVersion(name) {
  return JSON.parse(readFileSync(path.join(nodeModulesDir, name, 'package.json'), 'utf8')).version;
}

function emit(relativeTarget, content, provenance) {
  const target = path.join(VENDOR_DIR, relativeTarget);
  const bytes = Buffer.isBuffer(content) ? content : Buffer.from(content, 'utf8');
  writeOrCheck(target, bytes, drift);
  files[relativeTarget.split(path.sep).join('/')] = {
    ...provenance,
    sha256: sha256(bytes),
    bytes: bytes.length,
  };
}

function copyFromPackage(packageName, sourcePath, relativeTarget, transform) {
  const source = readFileSync(path.join(nodeModulesDir, packageName, sourcePath));
  const content = transform ? Buffer.from(transform.apply(source.toString('utf8')), 'utf8') : source;
  emit(relativeTarget, content, {
    package: packageName,
    version: packageVersion(packageName),
    source: sourcePath,
    ...(transform ? { transform: transform.name } : {}),
  });
}

const stripSourceMapComment = {
  name: 'strip-source-map-comment',
  apply: (text) => text.replace(/\n?\/\/# sourceMappingURL=\S+\s*$/, '\n'),
};

// --- Scripts and base CSS -------------------------------------------------------------
copyFromPackage('htmx.org', 'dist/htmx.min.js', 'htmx/htmx.min.js');
copyFromPackage('chart.js', 'dist/chart.umd.min.js', 'chartjs/chart.umd.min.js', stripSourceMapComment);
copyFromPackage(
  'chartjs-adapter-date-fns',
  'dist/chartjs-adapter-date-fns.bundle.min.js',
  'chartjs/chartjs-adapter-date-fns.bundle.min.js',
);
copyFromPackage(
  'chartjs-plugin-annotation',
  'dist/chartjs-plugin-annotation.min.js',
  'chartjs/chartjs-plugin-annotation.min.js',
);
copyFromPackage('modern-normalize', 'modern-normalize.css', 'modern-normalize/modern-normalize.css');

// --- Variable fonts (latin + latin-ext, upright only) ----------------------------------
const FONT_SOURCES = [
  { packageName: '@fontsource-variable/mona-sans', css: 'wdth.css', faces: ['latin-ext-wdth-normal', 'latin-wdth-normal'] },
  { packageName: '@fontsource-variable/geist-mono', css: 'wght.css', faces: ['latin-ext-wght-normal', 'latin-wght-normal'] },
];
const fontCss = [
  '/* Self-hosted variable fonts (SIL OFL 1.1). GENERATED FILE - DO NOT EDIT.\n'
    + ' * Rebuild: cd ui_web/frontend && npm run build:vendor */\n',
];
for (const { packageName, css, faces } of FONT_SOURCES) {
  const source = readFileSync(path.join(nodeModulesDir, packageName, css), 'utf8');
  const blocks = new Map(
    [...source.matchAll(/\/\* ([a-z0-9-]+) \*\/\s*(@font-face\s*\{[^}]*\})/g)].map((match) => [match[1], match[2]]),
  );
  for (const face of faces) {
    const key = [...blocks.keys()].find((name) => name.endsWith(`-${face}`));
    if (!key) {
      throw new Error(`Font face ${face} not found in ${packageName}/${css}`);
    }
    const fileName = `${key}.woff2`;
    copyFromPackage(packageName, `files/${fileName}`, path.join('fonts', fileName));
    fontCss.push(blocks.get(key).replace(/url\(\.\/files\/([^)]+)\)/, 'url("$1")') + '\n');
  }
}
emit(path.join('fonts', 'fonts.css'), fontCss.join('\n'), { generated: true });

// --- Iconoir subset ------------------------------------------------------------------
const ICON_SCAN_ROOTS = [
  { dir: path.join(uiWebDir, 'templates'), extensions: ['.html'] },
  { dir: path.join(repoRoot, 'project_management', 'reporting', 'templates'), extensions: ['.html'] },
  { dir: path.join(staticDir, 'js'), extensions: ['.js'], skip: [path.join(staticDir, 'js', 'report_editor', 'vendor')] },
  { dir: uiWebDir, extensions: ['.py'], skip: [path.join(uiWebDir, 'tests'), path.join(uiWebDir, 'frontend')] },
];

function walk(dir, extensions, skip = []) {
  if (skip.some((skipped) => dir.startsWith(skipped)) || !existsSync(dir)) {
    return [];
  }
  return readdirSync(dir).flatMap((entry) => {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) {
      return entry === 'node_modules' || entry === '__pycache__' ? [] : walk(full, extensions, skip);
    }
    return extensions.includes(path.extname(entry)) ? [full] : [];
  });
}

const iconUsage = new Map();
for (const root of ICON_SCAN_ROOTS) {
  for (const file of walk(root.dir, root.extensions, root.skip)) {
    for (const match of readFileSync(file, 'utf8').matchAll(/\biconoir-([a-z0-9]+(?:-[a-z0-9]+)*)/g)) {
      if (!iconUsage.has(match[1])) {
        iconUsage.set(match[1], repoRelative(file));
      }
    }
  }
}
const iconRoot = path.join(nodeModulesDir, 'iconoir', 'icons');

function iconSource(name) {
  // Iconoir's own CSS exposes solid variants as `iconoir-<name>-solid`.
  return name.endsWith('-solid') ? `icons/solid/${name.slice(0, -'-solid'.length)}.svg` : `icons/regular/${name}.svg`;
}

const icons = [...iconUsage.keys()].sort();
const unknown = icons.filter((name) => !existsSync(path.join(iconRoot, '..', iconSource(name))));
if (unknown.length) {
  console.error('Unknown iconoir icons (not in iconoir/icons/regular or iconoir/icons/solid):');
  for (const name of unknown) {
    console.error(`  - iconoir-${name} (first used in ${iconUsage.get(name)})`);
  }
  process.exit(1);
}
for (const name of icons) {
  copyFromPackage('iconoir', iconSource(name), path.join('iconoir', `${name}.svg`));
}
const iconSelectors = icons.map((name) => `.iconoir-${name}`).join(',\n');
const iconCss = [
  `/* Iconoir ${packageVersion('iconoir')} subset (MIT). GENERATED FILE - DO NOT EDIT.\n`
    + ' * Icons are discovered from templates, JS and ui_web Python sources.\n'
    + ' * Rebuild: cd ui_web/frontend && npm run build:vendor */\n',
  `${iconSelectors} {\n`
    + '  display: inline-block;\n'
    + '  flex: none;\n'
    + '  width: 1em;\n'
    + '  height: 1em;\n'
    + '  vertical-align: -0.125em;\n'
    + '  background-color: currentcolor;\n'
    + '  -webkit-mask: var(--icon) center / contain no-repeat;\n'
    + '  mask: var(--icon) center / contain no-repeat;\n'
    + '}\n',
  ...icons.map((name) => `.iconoir-${name} { --icon: url("${name}.svg"); }`),
  '',
].join('\n');
emit(path.join('iconoir', 'iconoir.css'), iconCss, { generated: true });

// --- Notices and manifest -------------------------------------------------------------
const LICENSES = [
  ['htmx.org', 'LICENSE'],
  ['chart.js', 'LICENSE.md'],
  ['chartjs-adapter-date-fns', 'LICENSE.md'],
  ['chartjs-plugin-annotation', 'LICENSE.md'],
  ['modern-normalize', 'license'],
  ['iconoir', 'LICENSE'],
  ['@fontsource-variable/mona-sans', 'LICENSE'],
  ['@fontsource-variable/geist-mono', 'LICENSE'],
];
const notices = [
  '# Third-party notices for ui_web/static/vendor',
  '',
  'Generated by `ui_web/frontend/scripts/build-vendor.mjs`. Do not edit.',
  'The date-fns library is bundled inside chartjs-adapter-date-fns (MIT).',
  '',
  ...LICENSES.flatMap(([name, file]) => [
    `## ${name} ${packageVersion(name)}`,
    '',
    '```text',
    normalizeNewlines(readFileSync(path.join(nodeModulesDir, name, file), 'utf8')).trim(),
    '```',
    '',
  ]),
].join('\n');
emit('THIRD_PARTY_NOTICES.md', notices, { generated: true });

const managedPaths = new Set([...Object.keys(files), 'asset-manifest.json']);
const runtimePackages = Object.keys(packageJson.dependencies).sort();
const manifest = {
  schema_version: 1,
  generator: 'ui_web/frontend/scripts/build-vendor.mjs',
  build_command: 'cd ui_web/frontend && npm ci && npm run build',
  package_json: 'ui_web/frontend/package.json',
  package_json_sha256: sha256(normalizeNewlines(readFileSync(path.join(frontendDir, 'package.json'), 'utf8'))),
  package_lock: 'ui_web/frontend/package-lock.json',
  package_lock_sha256: sha256(normalizeNewlines(readFileSync(path.join(frontendDir, 'package-lock.json'), 'utf8'))),
  packages: Object.fromEntries(runtimePackages.map((name) => [name, packageVersion(name)])),
  icons,
  files: Object.fromEntries(Object.entries(files).sort(([left], [right]) => left.localeCompare(right))),
};
writeOrCheck(path.join(VENDOR_DIR, 'asset-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, drift);

// Remove files that are no longer produced so the vendor tree mirrors the manifest exactly.
for (const file of walk(VENDOR_DIR, ['.js', '.css', '.svg', '.woff2', '.md', '.json'])) {
  const relative = path.relative(VENDOR_DIR, file).split(path.sep).join('/');
  if (!managedPaths.has(relative)) {
    if (isCheckMode) {
      drift.push(`unexpected ${repoRelative(file)}`);
    } else {
      rmSync(file);
    }
  }
}

finishDriftCheck(drift, 'npm run build:vendor');
if (!isCheckMode) {
  console.log(`Vendored ${Object.keys(files).length} files (${icons.length} icons) into ${repoRelative(VENDOR_DIR)}`);
}
