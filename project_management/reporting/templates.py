from dataclasses import dataclass
from dataclasses import field
import hashlib
from importlib import resources
from typing import Mapping

from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_presentation import TemplateDefinition, TemplateSelection


RENDERER_VERSION = 'html-renderer/1'
DEFAULT_SECTION_ORDER = ('key_messages', 'changes', 'register', 'coverage')
DEFAULT_OPTIONAL_COLUMNS = ('summary_time',)
ALLOWED_GROUP_BY = {'none', 'status', 'assignee'}
ALLOWED_SORT_BY = {'key'}
ALLOWED_OPTIONAL_COLUMNS = {'source_hash', 'summary_time'}
REGISTERED_TEMPLATES = {
    ('daily-standup', '1'): ('daily_standup.html', ('body.html',)),
    ('weekly-timeline', '1'): ('weekly_timeline.html', ('body.html',)),
    ('daily-standup', '2'): ('daily_standup_authored.html', ('body_authored.html',)),
    ('weekly-timeline', '2'): ('weekly_timeline_authored.html', ('body_authored.html',)),
}


@dataclass(frozen=True, slots=True)
class RegisteredTemplate:
    template_id: str
    version: str
    content: str
    template_hash: str
    renderer_version: str = RENDERER_VERSION
    dependencies: Mapping[str, str] = field(default_factory=dict)


def load_default_registry() -> dict[tuple[str, str], RegisteredTemplate]:
    return {
        key: _load_registered_template(key[0], key[1], filename, dependency_names)
        for key, (filename, dependency_names) in REGISTERED_TEMPLATES.items()
    }


def resolve_template(registry: Mapping, selection: TemplateSelection) -> tuple[RegisteredTemplate, TemplateDefinition]:
    key = (selection.template_id, selection.version)
    template = registry.get(key)
    if template is None:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if (not isinstance(template, RegisteredTemplate)
            or template.template_id != selection.template_id
            or template.version != selection.version
            or template.renderer_version != RENDERER_VERSION
            or template.template_hash != template_hash(template.content, template.dependencies)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    options = normalize_options(selection.options)
    definition = TemplateDefinition(
        template_id=selection.template_id,
        version=selection.version,
        options=options,
        template_hash=template.template_hash,
        renderer_version=template.renderer_version,
    )
    return template, definition


def normalize_options(options: Mapping | None) -> dict:
    if options is None:
        options = {}
    if not isinstance(options, Mapping):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if set(options.keys()) - {'group_by', 'sort_by', 'section_order', 'optional_columns'}:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    group_by = options.get('group_by', 'none')
    sort_by = options.get('sort_by', 'key')
    section_order = _section_order(options.get('section_order', DEFAULT_SECTION_ORDER))
    optional_columns = _optional_columns(options.get('optional_columns', DEFAULT_OPTIONAL_COLUMNS))
    if group_by not in ALLOWED_GROUP_BY or sort_by not in ALLOWED_SORT_BY:
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return {
        'group_by': group_by,
        'sort_by': sort_by,
        'section_order': section_order,
        'optional_columns': optional_columns,
    }


def _section_order(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    result = tuple(value)
    if any(type(item) is not str for item in result):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if set(result) != set(DEFAULT_SECTION_ORDER) or len(result) != len(DEFAULT_SECTION_ORDER):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return result


def _optional_columns(value) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    result = tuple(value)
    if any(type(item) is not str for item in result):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    if set(result) - ALLOWED_OPTIONAL_COLUMNS or len(result) != len(set(result)):
        raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
    return result


def template_hash(content: str, dependencies: Mapping[str, str]) -> str:
    parts = [content]
    for name in sorted(dependencies):
        parts.append(name)
        parts.append(dependencies[name])
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()


def _load_registered_template(
    template_id: str,
    version: str,
    filename: str,
    dependency_names,
) -> RegisteredTemplate:
    content = _read_template(filename)
    dependencies = {name: _read_template(name) for name in dependency_names}
    return RegisteredTemplate(
        template_id=template_id,
        version=version,
        content=content,
        template_hash=template_hash(content, dependencies),
        dependencies=dict(dependencies),
    )


def _read_template(filename: str) -> str:
    return (
        resources.files(__package__)
        .joinpath('templates')
        .joinpath(filename)
        .read_text(encoding='utf-8')
    )
