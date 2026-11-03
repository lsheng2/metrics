import configparser
import json
from io import StringIO
from pathlib import Path

from project_management.app.domain.captures import ArchiveError
from .git import OPTIONS
from .paths import read_bytes, validate_directory, write_bytes


def write_configuration(archive, hooks, author_name, author_email):
    parser = configparser.RawConfigParser()
    parser['core'] = {
        'repositoryformatversion': '0', 'filemode': 'false', 'bare': 'false',
        'logallrefupdates': 'true', 'symlinks': 'false', 'ignorecase': 'true',
        'hookspath': str(hooks),
    }
    for key, value in OPTIONS.items():
        section, option = key.split('.', 1)
        if section not in parser:
            parser[section] = {}
        parser[section][option] = value
    parser['user'] = {'name': author_name, 'email': author_email}
    for section in parser.sections():
        for key, value in parser[section].items():
            parser[section][key] = json.dumps(value, ensure_ascii=False)
    output = StringIO()
    parser.write(output)
    write_bytes(archive / '.git', 'config', output.getvalue().encode('utf-8'))


def validate_configuration(archive, hooks, author_name, author_email):
    metadata = archive / '.git'
    validate_directory(metadata)
    validate_directory(hooks)
    if next(hooks.iterdir(), None) is not None:
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    for name in ('commondir', 'shallow', 'info/grafts', 'info/attributes', 'objects/info/alternates', 'refs/replace'):
        if (metadata / name).exists():
            raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    if read_bytes(metadata, 'HEAD', limit=512).strip() != b'ref: refs/heads/main':
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
    parser = configparser.RawConfigParser()
    try:
        parser.read_string(read_bytes(metadata, 'config', limit=65536).decode('utf-8'))
    except (ValueError, configparser.Error, UnicodeError):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID') from None
    expected = {key.lower(): value for key, value in OPTIONS.items()}
    expected.update({'core.hookspath': str(hooks), 'user.name': author_name, 'user.email': author_email})
    core = {'core.repositoryformatversion', 'core.filemode', 'core.bare', 'core.logallrefupdates',
            'core.symlinks', 'core.ignorecase'}
    try:
        actual = {section.lower() + '.' + key.lower(): json.loads(value)
                  for section in parser.sections() for key, value in parser[section].items()}
    except (ValueError, TypeError):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID') from None
    if (actual.keys() - expected.keys() - core or any(actual.get(key) != value for key, value in expected.items())
            or actual.get('core.bare') != 'false' or actual.get('core.repositoryformatversion') != '0'):
        raise ArchiveError('ARCHIVE_CONFIG_INVALID')
