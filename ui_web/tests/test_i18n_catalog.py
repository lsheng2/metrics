"""zh-Hans localization gates: catalog completeness, compiled-catalog sync and shell copy."""

import ast
import gettext
import os
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import templatize

from ui_web.workbench_service_status import DASHBOARD_RESTART_COMMAND, DEFAULT_FULL_STACK_LAUNCHER_COMMAND

UI_WEB = Path(__file__).resolve().parents[1]
CATALOG = UI_WEB / 'locale' / 'zh_Hans' / 'LC_MESSAGES' / 'django'
UNSCANNED_DIRECTORIES = frozenset({'tests', 'migrations', 'frontend', 'static', 'locale', 'node_modules', '__pycache__'})
GETTEXT_FUNCTIONS = frozenset({
    '_', 'gettext', 'gettext_lazy', 'gettext_noop', 'ngettext', 'ngettext_lazy',
    'pgettext', 'pgettext_lazy', 'npgettext', 'npgettext_lazy',
})
STRING_LITERAL = r"""u(?:'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")"""
TEMPLATIZED_CALL = re.compile(rf'\b(?P<function>n?p?gettext)\((?P<arguments>{STRING_LITERAL}(?:\s*,\s*{STRING_LITERAL})*)')
PO_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
PLACEHOLDER = re.compile(r'%\(\w+\)s')
ENGLISH_WORD = re.compile(r'[A-Za-z][A-Za-z_]+')
# Brand, product names, key names and acronyms stay English in every language; commands are
# injected through placeholders and are stripped verbatim before the check.
SHELL_VERBATIM_WORDS = frozenset({'Metrics', 'Dashboard', 'Grafana', 'AI', 'Base', 'Ctrl', 'WAF'})
SHELL_VERBATIM_COMMANDS = (DEFAULT_FULL_STACK_LAUNCHER_COMMAND, DASHBOARD_RESTART_COMMAND)
SHELL_COPY_ATTRIBUTES = frozenset({'aria-label', 'title', 'placeholder', 'alt'})
NON_SHELL_ELEMENTS = frozenset({'head', 'main', 'script', 'style', 'kbd'})
SHELL_BLOCK = re.compile(r'\{% block (?P<name>title|page_title|breadcrumbs|header_extra) %\}(?P<body>.*?)\{% endblock %\}', re.S)
TEMPLATE_MARKUP = re.compile(r'\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}|<[^>]*>', re.S)


def _message_key(function: str, strings: list) -> tuple[str, str] | None:
    needed = 2 if function.startswith(('p', 'np')) else 1
    if len(strings) < needed or not all(isinstance(value, str) for value in strings[:needed]):
        return None
    return (strings[0], strings[1]) if needed == 2 else ('', strings[0])


def _template_messages():
    for path in sorted((UI_WEB / 'templates').rglob('*.html')):
        for match in TEMPLATIZED_CALL.finditer(templatize(path.read_text(encoding='utf-8'), origin=str(path))):
            strings = [ast.literal_eval(value) for value in re.findall(STRING_LITERAL, match['arguments'])]
            yield _message_key(match['function'], strings), path


def _python_messages():
    for directory, subdirectories, files in os.walk(UI_WEB):
        subdirectories[:] = [name for name in subdirectories if name not in UNSCANNED_DIRECTORIES]
        for name in sorted(files):
            if not name.endswith('.py'):
                continue
            path = Path(directory) / name
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'), filename=str(path))):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, 'attr', '')
                if function in GETTEXT_FUNCTIONS:
                    strings = [arg.value if isinstance(arg, ast.Constant) else None for arg in node.args]
                    yield _message_key(function, strings), path


def _po_unescape(quoted: str) -> str:
    body = PO_STRING.fullmatch(quoted.strip())[1]
    return re.sub(r'\\(.)', lambda escape: {'n': '\n', 't': '\t'}.get(escape[1], escape[1]), body)


def _po_entries() -> dict[tuple[str, str], str]:
    entries, entry, field = {}, {}, ''
    for line in CATALOG.with_suffix('.po').read_text(encoding='utf-8').splitlines() + ['']:
        if not line.strip():
            if 'msgid' in entry:
                entries[(entry.get('msgctxt', ''), entry['msgid'])] = entry.get('msgstr', entry.get('msgstr[0]', ''))
            entry, field = {}, ''
        elif line.startswith('"'):
            entry[field] += _po_unescape(line)
        elif not line.startswith('#'):
            field, _, value = line.partition(' ')
            entry[field] = _po_unescape(value)
    entries.pop(('', ''), None)
    return entries


class _ShellCopy(HTMLParser):
    """Collects text and accessible names rendered by the shell, outside the page's <main>."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.copy = []

    def handle_starttag(self, tag, attrs):
        if tag in NON_SHELL_ELEMENTS:
            self.depth += 1
        if not self.depth:
            self.copy.extend(value for name, value in attrs if value and (
                name in SHELL_COPY_ATTRIBUTES or name.startswith(('data-message-', 'data-theme-hint-'))))

    def handle_endtag(self, tag):
        if tag in NON_SHELL_ELEMENTS:
            self.depth -= 1

    def handle_data(self, data):
        if not self.depth:
            self.copy.append(data)


def _without_commands(text: str) -> str:
    for command in SHELL_VERBATIM_COMMANDS:
        text = text.replace(command, '')
    return text


class TestZhHansCatalog(SimpleTestCase):
    def test_shouldTranslateEveryUiWebMessage(self):
        # Given
        entries = _po_entries()
        messages = [*_template_messages(), *_python_messages()]

        # Then
        self.assertLessEqual({('', 'Skip to content'), ('service state', 'connected')}, {key for key, _ in messages})
        untranslated = sorted({f'{path.relative_to(UI_WEB)}: {key}' for key, path in messages if key and not entries.get(key)})
        self.assertEqual([], untranslated)

    def test_shouldShipCompiledCatalogMatchingPo(self):
        # Given
        with CATALOG.with_suffix('.mo').open('rb') as handle:
            compiled = gettext.GNUTranslations(handle)

        # Then
        stale = sorted(
            key for key, msgstr in _po_entries().items()
            if msgstr and (compiled.pgettext(*key) if key[0] else compiled.gettext(key[1])) != msgstr
        )
        self.assertEqual([], stale)

    def test_shouldKeepFormatPlaceholdersInTranslations(self):
        broken = sorted(
            key for key, msgstr in _po_entries().items()
            if msgstr and sorted(PLACEHOLDER.findall(key[1])) != sorted(PLACEHOLDER.findall(msgstr))
        )
        self.assertEqual([], broken)

    def test_shouldTranslateShellBlocksInEveryTemplate(self):
        # Given: page templates fill the tab title and topbar crumbs, which belong to the shell.
        blocks = [
            (path.relative_to(UI_WEB / 'templates').as_posix(), match)
            for path in sorted((UI_WEB / 'templates').rglob('*.html'))
            for match in SHELL_BLOCK.finditer(path.read_text(encoding='utf-8'))
        ]

        # Then
        self.assertIn(('bug_trend_scope_audit.html', 'breadcrumbs'), {(name, match['name']) for name, match in blocks})
        bare = sorted(
            f'{name}: {match["name"]}' for name, match in blocks
            if set(ENGLISH_WORD.findall(TEMPLATE_MARKUP.sub(' ', match['body']))) - SHELL_VERBATIM_WORDS
        )
        self.assertEqual([], bare)


class TestZhHansShellCopy(TestCase):
    def test_shouldRenderShellWithoutUntranslatedEnglish(self):
        # Given
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'zh-hans'

        # When
        with tempfile.TemporaryDirectory() as state_dir:
            with override_settings(METRICS_STATE_DIR=state_dir):
                response = self.client.get(reverse('ui_web:homepage'))

        # Then
        self.assertEqual(200, response.status_code)
        shell = _ShellCopy()
        shell.feed(response.content.decode('utf-8'))
        self.assertIn('跟随系统主题', shell.copy)
        leaks = sorted({
            text.strip() for text in shell.copy
            if set(ENGLISH_WORD.findall(_without_commands(text))) - SHELL_VERBATIM_WORDS
        })
        self.assertEqual([], leaks)
