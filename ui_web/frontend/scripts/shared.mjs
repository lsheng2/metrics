import { createHash } from 'node:crypto';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const frontendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const uiWebDir = path.resolve(frontendDir, '..');
export const repoRoot = path.resolve(uiWebDir, '..');
export const staticDir = path.join(uiWebDir, 'static');
export const nodeModulesDir = path.join(frontendDir, 'node_modules');

export const isCheckMode = process.argv.includes('--check');

export function normalizeNewlines(text) {
  return text.replace(/\r\n/g, '\n');
}

export function sha256(content) {
  return createHash('sha256').update(content).digest('hex');
}

export function repoRelative(filePath) {
  return path.relative(repoRoot, filePath).split(path.sep).join('/');
}

/**
 * Writes generated content, or in --check mode reports whether the file on disk differs.
 * Text content is compared with normalized newlines; Buffers are compared byte-for-byte.
 */
export function writeOrCheck(filePath, content, drift) {
  const exists = existsSync(filePath);
  if (isCheckMode) {
    if (!exists) {
      drift.push(`missing ${repoRelative(filePath)}`);
      return;
    }
    const current = readFileSync(filePath);
    const same = Buffer.isBuffer(content)
      ? current.equals(content)
      : normalizeNewlines(current.toString('utf8')) === normalizeNewlines(content);
    if (!same) {
      drift.push(`stale ${repoRelative(filePath)}`);
    }
    return;
  }
  mkdirSync(path.dirname(filePath), { recursive: true });
  writeFileSync(filePath, content);
}

export function finishDriftCheck(drift, rebuildCommand) {
  if (!isCheckMode) {
    return;
  }
  if (drift.length) {
    console.error(`Generated assets are out of date (${drift.length}):`);
    for (const line of drift) {
      console.error(`  - ${line}`);
    }
    console.error(`Run: cd ui_web/frontend && ${rebuildCommand}`);
    process.exit(1);
  }
  console.log('Generated assets are up to date.');
}
