import importlib
import json
from types import SimpleNamespace

from django.test import override_settings
import pytest

from scripts.validation.project_full_stack_support import json_lines
from scripts.validation.project_week_browser import dispatch_count
from scripts.validation.project_week_data import WEEK_QUERY


@pytest.fixture
def restore_factories(monkeypatch):
    from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
    from project_management.app.api import report_factories, run_factories
    from provider_sync.app.api import access_factory, references

    monkeypatch.setattr(
        ProjectProviderProfileRegistry, 'load_default',
        ProjectProviderProfileRegistry.__dict__['load_default'],
    )
    for module, name in (
        (access_factory, 'create_provider_access_service'),
        (run_factories, 'create_provider_access_service'),
        (references, 'create_provider_reference_reader'),
        (report_factories, 'create_provider_reference_reader'),
    ):
        monkeypatch.setattr(module, name, getattr(module, name))


def activate_fixture(run_dir, scenario):
    module = importlib.import_module('scripts.validation.project_ui_fixture_app')
    with override_settings(
        RUN_DIR=run_dir, METRICS_PROJECT_VALIDATION_SCENARIO=scenario,
        METRICS_PROJECT_PROFILE_RECORDS_OVERRIDE=[],
    ):
        module.ProjectRunFixtureAppConfig(module.__name__, module).ready()


def test_week_completion_factory_uses_synthetic_reference_reader(tmp_path, restore_factories):
    from ui_web.views.report_completion import ReportDraftCompletionView

    (tmp_path / 'evidence').mkdir()
    activate_fixture(tmp_path, 'full-week')
    with override_settings(
        METRICS_PROJECT_ARCHIVE_ROOT=str(tmp_path / 'archive'),
        METRICS_PROJECT_ARCHIVE_AUTHOR_NAME='Synthetic Author',
        METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL='synthetic@example.test',
    ):
        reader = ReportDraftCompletionView.completion_factory().reference_reader
    stage = SimpleNamespace(descriptor=SimpleNamespace(query=WEEK_QUERY))
    assert reader.supports(stage, 'principal-1')
    assert not reader.supports(stage, 'different-principal')
    assert not reader.supports(SimpleNamespace(descriptor=SimpleNamespace(query='other')), 'principal-1')
    member = SimpleNamespace(
        provider_id='jira', endpoint_id='synthetic-endpoint', stable_id='101', display_key='ALPHA-101',
    )
    observation = reader.read({'membership_proof_hash': 'a' * 64}, member)
    assert observation.identity['stable_id'] == '101'
    assert observation.canonical_url.endswith('/browse/ALPHA-101')
    assert json_lines(tmp_path / 'evidence/reference-requests.jsonl') == [
        {'stable_id': '101', 'scope_hash': 'a' * 64},
    ]


def test_single_run_fixture_keeps_completion_disabled(tmp_path, restore_factories):
    from provider_sync.app.api import references

    activate_fixture(tmp_path, 'single')
    assert not references.create_provider_reference_reader().supports(
        SimpleNamespace(descriptor=SimpleNamespace(query=WEEK_QUERY)), 'principal-1',
    )


def test_week_dispatch_counter_reads_current_model_receipts(tmp_path):
    directory = tmp_path / 'model'
    directory.mkdir()
    (directory / 'executor-observations.jsonl').write_text(
        ''.join(json.dumps({'kind': 'project_summary', 'id': number}) + '\n' for number in (1, 2, 3)),
        encoding='utf-8',
    )
    assert dispatch_count(tmp_path) == 3
