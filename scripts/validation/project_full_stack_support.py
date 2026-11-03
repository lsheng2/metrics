from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from enum import Enum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import socket
import uuid


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = Path('D:/AIGC/scrum_dashboard_validation/full-stack')
OWNER = 'dashboard-manual-fullstack'
ROOT_OWNER = 'dashboard-manual-fullstack-root'
SCHEMA_VERSION = 1
ALLOWED_ENV_KEYS = {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'HOME', 'USERPROFILE', 'TEMP', 'TMP', 'NO_PROXY'}
UUID_TEXT = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


def json_ready(value):
    if is_dataclass(value):
        return json_ready(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value, *, replace=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(json_ready(value), ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if replace:
        temporary = path.with_name(f'{path.name}.tmp-{os.getpid()}')
        temporary.write_text(data, encoding='utf-8')
        os.replace(temporary, path)
        return
    with path.open('x', encoding='utf-8') as stream:
        stream.write(data)


def digest_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def is_reparse_or_symlink(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, 'is_junction', None)
    return bool(is_junction and is_junction())


def reject_reparse_components(path: Path) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = Path(current) / part
        if current.exists() and is_reparse_or_symlink(current):
            raise ValueError('Refusing reparse or symlink path component.')


def validate_data_root(value: Path | str) -> Path:
    requested = Path(value)
    repo = REPO_ROOT.resolve()
    if not requested.is_absolute():
        raise ValueError('Validation data root must be an absolute canonical path.')
    reject_reparse_components(requested)
    root = requested.resolve(strict=False)
    if root != requested.absolute():
        raise ValueError('Validation data root must be an absolute canonical path.')
    if root == repo or root.is_relative_to(repo) or repo.is_relative_to(root):
        raise ValueError('Validation data root must be outside code repositories.')
    if any((parent / '.git').exists() for parent in (root, *root.parents)):
        raise ValueError('Validation data root must not be inside a Git worktree.')
    return root


def root_owner_payload(root: Path) -> dict:
    return {'schema_version': SCHEMA_VERSION, 'owner': ROOT_OWNER, 'repository': str(REPO_ROOT.resolve()), 'data_root': str(root)}


def ensure_data_root(value: Path | str) -> Path:
    root = validate_data_root(value)
    marker = root / 'owner.json'
    identity = root_owner_payload(root)
    if root.exists():
        if not root.is_dir():
            raise ValueError('Validation data root is not a directory.')
        if marker.exists():
            if read_json(marker) != identity:
                raise ValueError('Validation data root has another owner.')
        elif any(root.iterdir()):
            raise ValueError('Refusing existing nonempty unowned validation data root.')
    root.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        write_json(marker, identity)
    return root


def create_run_dir(data_root: Path) -> Path:
    for _ in range(16):
        run_uuid = str(uuid.uuid4())
        run_dir = data_root / run_uuid
        try:
            run_dir.mkdir()
            return run_dir
        except FileExistsError:
            continue
    raise RuntimeError('Could not allocate a fresh validation run directory.')


def owner_payload(run_dir: Path, data_root: Path) -> dict:
    return {
        'schema_version': SCHEMA_VERSION,
        'owner': OWNER,
        'repository': str(REPO_ROOT.resolve()),
        'data_root': str(data_root.resolve()),
        'run_directory': str(run_dir.resolve()),
        'run_uuid': run_dir.name,
    }


def initialize_run_dir(run_dir: Path, data_root: Path) -> None:
    if UUID_TEXT.fullmatch(run_dir.name) is None:
        raise ValueError('Run directory name must be a canonical UUID.')
    for name in ('archive', 'base', 'environment', 'lifecycle', 'logs', 'evidence'):
        (run_dir / name).mkdir()
    write_json(run_dir / 'owner.json', owner_payload(run_dir, data_root))


def require_owned_run_dir(value: Path | str) -> Path:
    requested = Path(value)
    if not requested.is_absolute():
        raise ValueError('Run directory must be an absolute canonical path.')
    reject_reparse_components(requested)
    run_dir = requested.resolve(strict=True)
    if run_dir != requested.absolute() or UUID_TEXT.fullmatch(run_dir.name) is None:
        raise ValueError('Run directory must be an absolute canonical UUID path.')
    owner = read_json(run_dir / 'owner.json')
    data_root = validate_data_root(Path(owner['data_root']))
    marker = data_root / 'owner.json'
    if not marker.is_file() or read_json(marker) != root_owner_payload(data_root):
        raise ValueError('Owned data root marker is invalid.')
    if run_dir.parent != data_root:
        raise ValueError('Run directory must be a direct child of its owned data root.')
    expected = owner_payload(run_dir, data_root)
    if owner != expected:
        raise ValueError('Run directory is not owned by this qualification launcher.')
    return run_dir


def safe_url(port: int, route_path: str) -> str:
    if not isinstance(route_path, str) or not route_path.startswith('/'):
        raise ValueError('Route path must come from Django reverse().')
    return f'http://127.0.0.1:{port}{route_path}'


def base_environment(directory: Path, source_environment: dict[str, str] | None = None) -> dict[str, str]:
    source_environment = dict(os.environ if source_environment is None else source_environment)
    source = {key: value for key, value in source_environment.items() if key.upper() in ALLOWED_ENV_KEYS}
    home = directory / 'home'
    temp = directory / 'tmp'
    home.mkdir(parents=True, exist_ok=True)
    temp.mkdir(parents=True, exist_ok=True)
    source.update(HOME=str(home), USERPROFILE=str(home), TEMP=str(temp), TMP=str(temp), NO_PROXY='127.0.0.1,localhost')
    return source


def environment_digest(environment: dict[str, str]) -> str:
    return digest_bytes(json.dumps(environment, sort_keys=True, separators=(',', ':')).encode('utf-8'))


@contextmanager
def sanitized_process_environment(directory: Path):
    previous = dict(os.environ)
    allowed = base_environment(directory, previous)
    os.environ.clear()
    os.environ.update(allowed)
    try:
        yield dict(os.environ)
    finally:
        os.environ.clear()
        os.environ.update(previous)


def copy_if_exists(source: str | Path, target: Path) -> str | None:
    path = Path(source)
    if not path.exists():
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return str(target)


def json_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    values = []
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        try:
            values.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return values


def positive_int(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise ValueError('value must be positive')
    return number


def available_port(value: str) -> int:
    port = int(value)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.2)
        if probe.connect_ex(('127.0.0.1', port)) == 0:
            raise ValueError('explicit app port is not available')
    return port
