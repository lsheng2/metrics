from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import shutil
from time import monotonic

from provider_sync.app.api.access_contracts import AccessError
from provider_sync.out.jql_process import run_node


@dataclass(frozen=True, slots=True)
class ParsedJql:
    filter_ids: tuple[str, ...]
    functions: tuple[str, ...]


class JqlParser:
    resolver_version = 'jira-dc-v1:atlaskit-ast-4.2.0:parser-3.1.0:policy-1'

    def __init__(self, executable='node'):
        resolved = shutil.which(executable)
        if resolved is None:
            raise AccessError('SCOPE_UNVERIFIABLE')
        self.executable = str(Path(resolved).resolve())
        self.root = Path(__file__).with_name('_jql')

    def parse(self, jql, *, seconds=5):
        if not isinstance(jql, str) or not jql.strip() or len(jql) > 16384 or seconds <= 0:
            raise AccessError('SCOPE_UNVERIFIABLE')
        payload = json.dumps(jql, ensure_ascii=False).encode('utf-8')
        if len(payload) > 65536:
            raise AccessError('SCOPE_UNVERIFIABLE')
        deadline = monotonic() + min(seconds, 5)
        try:
            manifest = json.loads((self.root / 'manifest.json').read_bytes())
            for name, field in [('parser.cjs', 'bundle_sha256'), ('THIRD-PARTY-LICENSES.txt', 'licenses_sha256')]:
                if hashlib.sha256((self.root / name).read_bytes()).hexdigest() != manifest[field]:
                    raise AccessError('SCOPE_UNVERIFIABLE')
            version = run_node(self.executable, ['--version'], b'', deadline - monotonic()).decode('ascii').strip()
            if version != 'v' + manifest['node_tested']:
                raise AccessError('SCOPE_UNVERIFIABLE')
            output = run_node(self.executable, [str(self.root / 'parser.cjs')], payload, deadline - monotonic())
            value = json.loads(output)
            if (set(value) != {'filter_ids', 'functions'}
                    or not isinstance(value['filter_ids'], list) or not isinstance(value['functions'], list)
                    or any(not isinstance(item, str) for item in value['filter_ids'] + value['functions'])):
                raise ValueError
            return ParsedJql(tuple(value['filter_ids']), tuple(value['functions']))
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            raise AccessError('SCOPE_UNVERIFIABLE') from None
