import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SETTINGS = 'scripts.validation.project_ui_settings'
FIXTURE_NAME = 'project-ui-w2'
OWNED_BASE = REPO_ROOT / '.tmp' / 'project-reporting-w2'
OWNER_FILE_NAME = '.project-ui-fixture-owner.json'
DB_FILE_NAME = 'project-ui.sqlite3'


class FixtureSafetyError(Exception):
    pass


def reject_conflicting_settings():
    configured = os.environ.get('DJANGO_SETTINGS_MODULE')
    if configured and configured != EXPECTED_SETTINGS:
        raise FixtureSafetyError(f'Refusing conflicting DJANGO_SETTINGS_MODULE={configured}.')


def default_fixture_root():
    stamp = datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    return OWNED_BASE / 'fixture-runs' / f'{FIXTURE_NAME}-{stamp}-{token_hex(4)}'


def owner_payload(fixture_root):
    return {
        'fixture_name': FIXTURE_NAME,
        'root': str(fixture_root.resolve()),
        'settings': EXPECTED_SETTINGS,
    }


def validate_bootstrap_root(raw_root):
    reject_conflicting_settings()
    fixture_root = Path(raw_root) if raw_root else default_fixture_root()
    validate_root_path(fixture_root)
    if fixture_root.exists() and any(fixture_root.iterdir()):
        validate_owner_file(fixture_root)
    db_path = fixture_root / DB_FILE_NAME
    if db_path.exists():
        validate_database_file(fixture_root, db_path)
    return fixture_root.resolve()


def validate_settings_startup(allow_bootstrap=False):
    fixture_root = Path(os.environ.get('METRICS_PROJECT_UI_FIXTURE_ROOT', ''))
    validate_root_path(fixture_root)
    validate_owner_file(fixture_root)
    db_path = fixture_root / DB_FILE_NAME
    if allow_bootstrap and not db_path.exists():
        return fixture_root.resolve()
    validate_database_file(fixture_root, db_path)
    return fixture_root.resolve()


def validate_root_path(fixture_root):
    lexical_root = fixture_root.absolute()
    lexical_base = OWNED_BASE.absolute()
    try:
        lexical_root.relative_to(lexical_base)
    except ValueError:
        raise FixtureSafetyError('Fixture root must stay inside .tmp/project-reporting-w2.')

    resolved_root = fixture_root.resolve(strict=False)
    resolved_base = OWNED_BASE.resolve(strict=False)
    try:
        resolved_root.relative_to(resolved_base)
    except ValueError:
        raise FixtureSafetyError('Fixture root must stay inside .tmp/project-reporting-w2.')

    reject_reparse_path(fixture_root)


def reject_reparse_path(fixture_root):
    check_existing_path(REPO_ROOT)
    current = REPO_ROOT
    try:
        relative_parts = OWNED_BASE.absolute().relative_to(REPO_ROOT.absolute()).parts
    except ValueError:
        relative_parts = ()
    for part in relative_parts:
        current = current / part
        check_existing_path(current)

    current = OWNED_BASE
    try:
        fixture_parts = fixture_root.absolute().relative_to(OWNED_BASE.absolute()).parts
    except ValueError:
        fixture_parts = ()
    for part in fixture_parts:
        current = current / part
        check_existing_path(current)


def check_existing_path(path):
    if path.exists() and is_reparse_or_symlink(path):
        raise FixtureSafetyError(f'Refusing reparse or symlink fixture path component: {path}.')


def is_reparse_or_symlink(path):
    if path.is_symlink():
        return True
    is_junction = getattr(path, 'is_junction', None)
    return bool(is_junction and is_junction())


def validate_owner_file(fixture_root):
    owner_path = fixture_root / OWNER_FILE_NAME
    if not owner_path.is_file():
        raise FixtureSafetyError('Refusing unowned fixture root with existing content.')
    if is_reparse_or_symlink(owner_path):
        raise FixtureSafetyError('Refusing reparse or symlink fixture owner file.')
    payload = json.loads(owner_path.read_text(encoding='utf-8'))
    if payload != owner_payload(fixture_root):
        raise FixtureSafetyError('Refusing fixture root owned by another validation run.')


def write_owner_file(fixture_root):
    owner_path = fixture_root / OWNER_FILE_NAME
    if owner_path.exists():
        validate_owner_file(fixture_root)
        return
    owner_path.write_text(json.dumps(owner_payload(fixture_root), sort_keys=True), encoding='utf-8')


def validate_database_file(fixture_root, db_path):
    if not db_path.is_file():
        raise FixtureSafetyError('Refusing fixture database without owner marker.')
    if is_reparse_or_symlink(db_path):
        raise FixtureSafetyError('Refusing reparse or symlink fixture database.')
    try:
        with sqlite3.connect(db_path) as connection:
            row = connection.execute(
                'SELECT fixture_name, fixture_root, settings_module '
                'FROM project_ui_fixture_owner WHERE fixture_name = ?',
                (FIXTURE_NAME,),
            ).fetchone()
    except sqlite3.DatabaseError as error:
        raise FixtureSafetyError(f'Refusing fixture database without owner marker: {error}.') from None
    expected = (FIXTURE_NAME, str(fixture_root.resolve()), EXPECTED_SETTINGS)
    if row != expected:
        raise FixtureSafetyError('Refusing fixture database owned by another root.')


def record_database_marker(fixture_root, db_path):
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'CREATE TABLE IF NOT EXISTS project_ui_fixture_owner '
            '(fixture_name TEXT PRIMARY KEY, fixture_root TEXT NOT NULL, settings_module TEXT NOT NULL)'
        )
        row = connection.execute(
            'SELECT fixture_root, settings_module FROM project_ui_fixture_owner WHERE fixture_name = ?',
            (FIXTURE_NAME,),
        ).fetchone()
        expected = (str(fixture_root.resolve()), EXPECTED_SETTINGS)
        if row is not None and row != expected:
            raise FixtureSafetyError('Refusing to reuse fixture database owned by another root.')
        connection.execute(
            'INSERT OR REPLACE INTO project_ui_fixture_owner '
            '(fixture_name, fixture_root, settings_module) VALUES (?, ?, ?)',
            (FIXTURE_NAME, str(fixture_root.resolve()), EXPECTED_SETTINGS),
        )
