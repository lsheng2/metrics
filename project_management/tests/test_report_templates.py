import pytest

from project_management.app.api import reports as report_api
from project_management.reporting.templates import RegisteredTemplate, load_default_registry, template_hash
from project_management.tests.report_render_fixtures import (
    daily_template,
    draft_id,
    hostile_edits,
    no_day_snapshot,
    safe_snapshot,
    too_many_day_snapshot,
    weekly_template,
)


def test_template_switch_preserves_source():
    snapshot = safe_snapshot()
    renderer = report_api.ReportRenderer()

    daily = renderer.render(
        snapshot,
        daily_template(group_by='assignee'),
        hostile_edits(snapshot),
        draft_id=draft_id(1),
        revision=1,
    )
    weekly = renderer.render(
        snapshot,
        weekly_template(),
        hostile_edits(snapshot),
        draft_id=draft_id(1),
        revision=1,
    )

    for rendered in (daily, weekly):
        text = rendered.plain_text
        assert 'DEMO-101' in text
        assert 'DEMO-102' in text
        assert 'summary-101' in text
        assert 'summary-102' in text
        assert 'row-source-101' in text
        assert 'row-source-102' in text
        assert 'membership: complete' in text
        assert 'source hash' in text
        assert rendered.content_language == 'en'
        assert rendered.html_document.startswith(b'<!doctype html>')
        assert rendered.html_fragment.startswith('<main')
        assert rendered.snapshot_hash == daily.snapshot_hash


def test_unknown_template_or_option_is_rejected():
    snapshot = safe_snapshot()
    renderer = report_api.ReportRenderer()
    bad_templates = (
        report_api.TemplateSelection('management-review', '1', {}),
        report_api.TemplateSelection('daily-standup', '3', {}),
        report_api.TemplateSelection('daily-standup', '1', {'raw_css': 'body{}'}),
        report_api.TemplateSelection('daily-standup', '1', {'prompt': 'rewrite'}),
        report_api.TemplateSelection('daily-standup', '1', {'path': '../x.html'}),
        report_api.TemplateSelection('daily-standup', '1', {'group_by': 'component'}),
        report_api.TemplateSelection('daily-standup', '1', {'sort_by': 'priority'}),
        report_api.TemplateSelection(
            'daily-standup',
            '1',
            {'section_order': ['key_messages', 'changes', 'register', 'register']},
        ),
        report_api.TemplateSelection('daily-standup', '1', {'optional_columns': ['source_url']}),
    )

    for template in bad_templates:
        with pytest.raises(report_api.ReportError) as error:
            renderer.render(snapshot, template, draft_id=draft_id(2), revision=1)
        assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_malformed_options_and_false_registry_hash_are_rejected():
    snapshot = safe_snapshot()
    renderer = report_api.ReportRenderer()
    bad_templates = (
        report_api.TemplateSelection('daily-standup', '1', {'section_order': object()}),
        report_api.TemplateSelection('daily-standup', '1', {'optional_columns': [['summary_time']]}),
    )

    for template in bad_templates:
        with pytest.raises(report_api.ReportError) as error:
            renderer.render(snapshot, template, draft_id=draft_id(3), revision=1)
        assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'

    registry = load_default_registry()
    good = registry[('daily-standup', '1')]
    registry[('daily-standup', '1')] = RegisteredTemplate(
        good.template_id,
        good.version,
        good.content,
        '0' * 64,
    )
    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer(registry=registry).template_definition(daily_template())
    assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_supplied_registry_cannot_replace_registered_template_with_self_hash():
    registry = load_default_registry()
    good = registry[('daily-standup', '1')]
    altered_content = good.content.replace('Daily standup report', 'Omitted report', 1)
    registry[('daily-standup', '1')] = RegisteredTemplate(
        good.template_id,
        good.version,
        altered_content,
        template_hash(altered_content, good.dependencies),
        dependencies=good.dependencies,
    )

    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer(registry=registry)

    assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_weekly_timeline_uses_only_supplied_dates():
    snapshot = safe_snapshot()
    rendered = report_api.ReportRenderer().render(
        snapshot,
        weekly_template(),
        draft_id=draft_id(4),
        revision=1,
    )

    assert '2026-11-01' in rendered.plain_text
    assert '2026-11-02' in rendered.plain_text
    assert '2026-10-31' not in rendered.plain_text
    assert 'No published report' in rendered.plain_text
    assert 'No changes' not in rendered.plain_text


def test_weekly_without_days_displays_current_baseline_only():
    rendered = report_api.ReportRenderer().render(
        no_day_snapshot(),
        weekly_template(),
        draft_id=draft_id(5),
        revision=1,
    )

    assert '2026-11-02' in rendered.plain_text
    assert 'initial-baseline / no-published-history' in rendered.plain_text
    assert '2026-11-01:' not in rendered.plain_text


def test_weekly_more_than_seven_days_is_report_limit():
    with pytest.raises(report_api.ReportError) as error:
        report_api.ReportRenderer().render(
            too_many_day_snapshot(),
            weekly_template(),
            draft_id=draft_id(6),
            revision=1,
        )

    assert error.value.code == 'REPORT_LIMIT'


def test_renderer_public_api_exports_actual_values_and_service():
    exported = set(report_api.__all__)

    assert 'ReportRenderer' in exported
    assert 'TemplateSelection' in exported
    assert 'ReportEdit' in exported
    assert 'TemplateDefinition' in exported
    assert 'RenderedReport' in exported
    assert report_api.ReportRenderer().template_definition(daily_template()).template_id == 'daily-standup'
