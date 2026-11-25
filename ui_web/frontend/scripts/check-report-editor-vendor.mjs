// Verifies the bundle, metafile, first-party source inputs and package pins against the generated manifest. Both sides
// hash bytes with CRLF folded to LF, so a core.autocrlf checkout verifies the same content the generator recorded.
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { repoRelative, repoRoot, sha256, staticDir } from './shared.mjs';

const VENDOR_DIR = path.join(staticDir, 'js', 'report_editor', 'vendor');
const manifestPath = path.join(VENDOR_DIR, 'asset-manifest.json');
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
if (manifest.schema_version !== 2 || !manifest.source_inputs_sha256
    || Array.isArray(manifest.source_inputs_sha256) || typeof manifest.source_inputs_sha256 !== 'object') {
  throw new Error('Report editor manifest requires its complete source input hashes.');
}

function lfBytes(filePath) {
  return Buffer.from(readFileSync(filePath).toString('latin1').replace(/\r\n/g, '\n'), 'latin1');
}

const pinned = [
  [path.join(VENDOR_DIR, manifest.bundle), manifest.bundle_sha256],
  [path.join(repoRoot, manifest.source_entry), manifest.source_entry_sha256],
  [path.join(repoRoot, manifest.metafile), manifest.metafile_sha256],
  [path.join(repoRoot, manifest.package_json), manifest.package_json_sha256],
  [path.join(repoRoot, manifest.package_lock), manifest.package_lock_sha256],
];
const drift = [];
const metadata = JSON.parse(readFileSync(path.join(repoRoot, manifest.metafile), 'utf8'));
const inputRoot = path.dirname(path.join(repoRoot, manifest.source_entry));
const expectedInputs = Object.keys(metadata.inputs)
  .filter(input => !input.split(/[\\/]/u).includes('node_modules'))
  .map(input => {
    const relative = path.relative(repoRoot, path.resolve(inputRoot, input));
    if (relative.startsWith(`..${path.sep}`) || path.isAbsolute(relative)) {
      throw new Error('Report editor source input is outside the repository.');
    }
    return relative.split(path.sep).join('/');
  }).sort();
if (!expectedInputs.includes(manifest.source_entry)
    || JSON.stringify(expectedInputs) !== JSON.stringify(Object.keys(manifest.source_inputs_sha256).sort())) {
  drift.push('first-party source input inventory differs from build metadata');
}
for (const input of expectedInputs) {
  pinned.push([path.join(repoRoot, input), manifest.source_inputs_sha256[input]]);
}
for (const [filePath, expected] of pinned) {
  if (!existsSync(filePath)) {
    drift.push(`missing ${repoRelative(filePath)}`);
  } else if (sha256(lfBytes(filePath)) !== expected) {
    drift.push(`sha256 differs from manifest: ${repoRelative(filePath)}`);
  }
}

if (drift.length) {
  console.error(`Report editor vendor drifted from ${repoRelative(manifestPath)} (${drift.length}):`);
  for (const line of drift) {
    console.error(`  - ${line}`);
  }
  console.error('Rebuild: python scripts/validation/build_report_editor_vendor.py');
  process.exit(1);
}
console.log(`Report editor vendor matches ${repoRelative(manifestPath)}.`);
