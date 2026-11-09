import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EDITOR_BUILD = ROOT / 'ui_web' / 'editor_build'
VENDOR = ROOT / 'ui_web' / 'static' / 'js' / 'report_editor' / 'vendor'
PACKAGE_JSON = EDITOR_BUILD / 'package.json'
PACKAGE_LOCK = EDITOR_BUILD / 'package-lock.json'
BUNDLE = VENDOR / 'milkdown.bundle.js'
METAFILE = VENDOR / 'milkdown.bundle.meta.json'
MANIFEST = VENDOR / 'asset-manifest.json'
LOCAL_NODE_MODULES = EDITOR_BUILD / 'node_modules'


def main():
    env = dependency_environment()
    run(['npm.cmd' if os.name == 'nt' else 'npm', 'run', 'build'], EDITOR_BUILD, env)
    MANIFEST.write_text(json.dumps(manifest_payload(), indent=2) + '\n', encoding='utf-8')
    print(json.dumps({
        'bundle_sha256': sha256(BUNDLE),
        'metafile_sha256': sha256(METAFILE),
        'manifest_sha256': sha256(MANIFEST),
    }, indent=2))


def dependency_environment():
    if bin_path(LOCAL_NODE_MODULES).exists():
        return os.environ.copy()
    run(['npm.cmd' if os.name == 'nt' else 'npm', 'ci'], EDITOR_BUILD, os.environ.copy())
    return os.environ.copy()


def bin_path(node_modules):
    return node_modules / '.bin' / ('esbuild.cmd' if os.name == 'nt' else 'esbuild')


def manifest_payload():
    return {
        'schema_version': 1,
        'bundle': 'milkdown.bundle.js',
        'bundle_sha256': sha256(BUNDLE),
        'source_entry': 'ui_web/editor_build/report_milkdown.js',
        'package_json': 'ui_web/editor_build/package.json',
        'package_json_sha256': sha256(PACKAGE_JSON),
        'package_lock': 'ui_web/editor_build/package-lock.json',
        'package_lock_sha256': sha256(PACKAGE_LOCK),
        'metafile': 'ui_web/static/js/report_editor/vendor/milkdown.bundle.meta.json',
        'metafile_sha256': sha256(METAFILE),
        'pinned_package': '@milkdown/kit@7.23.0',
        'bundler': 'esbuild@0.28.2',
        'build_command': 'cd ui_web/editor_build && npm run build',
    }


def sha256(path):
    # CRLF is folded to LF so a core.autocrlf checkout records the hash npm run check verifies.
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def run(command, cwd, env):
    completed = subprocess.run(command, cwd=cwd, text=True, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


if __name__ == '__main__':
    sys.exit(main())
