import hashlib
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def source_identity():
    paths = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], timeout=15,
    ).decode('utf-8').split('\0')
    prefixes = ('ai_host/', 'project_management/', 'provider_sync/', 'bug_metrics/', 'ui_web/', 'metrics/', 'scripts/')
    files = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in sorted(set(paths))
        if name.startswith(prefixes) and (ROOT / name).is_file()
        and Path(name).suffix in {'.py', '.json', '.js', '.css', '.html'}
    }
    return {
        'commit': subprocess.check_output(
            ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, timeout=15,
        ).strip(),
        'kind': 'working_tree_not_clean_commit',
        'files': files,
    }
