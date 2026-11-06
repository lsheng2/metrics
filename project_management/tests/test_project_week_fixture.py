import asyncio
from copy import deepcopy
import importlib
import json
from types import SimpleNamespace

import pytest

from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.tests.summary_fixtures import PACK_ROOT, SummaryScenario
from scripts.validation.project_full_stack import build_parser
from scripts.validation.project_full_stack_base import ExactDynamicVectorExecutor, load_profile
from scripts.validation.project_full_stack_fixture import build_vector


def fixture():
    module = importlib.import_module('scripts.validation.project_week_fixture')
    scenario = SummaryScenario()
    scenario.setUp()
    return module, scenario


def test_shouldAllowOnlyNamedFullStackScenariosAndKeepDefault():
    parser = build_parser()
    assert parser.parse_args(['prepare']).scenario == 'single'
    assert parser.parse_args(['prepare', '--scenario', 'full-week']).scenario == 'full-week'
    with pytest.raises(SystemExit):
        parser.parse_args(['prepare', '--scenario', 'other.module'])


def test_shouldBindScenarioToKnownSettingsAndVectorShape():
    scenarios = importlib.import_module('scripts.validation.project_week_scenarios')
    assert scenarios.settings_for('single') == 'scripts.validation.project_full_stack_settings'
    assert scenarios.settings_for('full-week') == 'scripts.validation.project_week_settings'
    assert scenarios.validate_scenario({}, {'schema_version': 1}) == 'single'
    with pytest.raises(ValueError):
        scenarios.settings_for('untrusted.module')
    module, sample = fixture()
    vector = module.build_week_vector(sample.project.id, sample.stage)
    assert scenarios.validate_scenario({'scenario': 'full-week'}, vector) == 'full-week'
    for manifest, value in (({}, vector), ({'scenario': 'single'}, vector),
                            ({'scenario': 'full-week'}, {'schema_version': 1})):
        with pytest.raises(ValueError):
            scenarios.validate_scenario(manifest, value)


def test_shouldBuildThreeDistinctStableVectorsAndPreserveSingleVector(tmp_path):
    module, scenario = fixture()
    vector = module.build_week_vector(scenario.project.id, scenario.stage)
    assert vector['schema_version'] == 2
    assert [item['input_template']['binding']['stable_id'] for item in vector['cases']] == ['101', '102', '103']
    assert {row['fields']['status']['name'] for row in module.week_issues()} >= {'Fixed', 'In Analysis'}
    assert canonical_bytes(module.week_issues()) == canonical_bytes(module.week_issues())
    assert build_vector(scenario.project.id, scenario.stage)['schema_version'] == 1
    profile = load_profile(PACK_ROOT)
    executor = ExactDynamicVectorExecutor(
        {**vector, 'schema_documents': profile['schemaDocuments']}, tmp_path / 'observations.jsonl',
        profile['inputSchema'],
    )
    for index, case in enumerate(vector['cases'], 1):
        value = dynamic_input(case['input_template'], f'71000000-0000-4000-8000-{index:012d}')
        output = asyncio.run(executor.execute(SimpleNamespace(
            messages=(('user', canonical_bytes(value).decode()),), effective_input_sha256='a' * 64,
        )))
        result = json.loads(output)
        assert result['binding'] == value['binding']
        assert result['target_capture_id'] == value['target_capture_id']
    assert len((tmp_path / 'observations.jsonl').read_text().splitlines()) == 3


def test_shouldRejectUnknownOrChangedWeekInputBeforeDispatchReceipt(tmp_path):
    module, scenario = fixture()
    vector = module.build_week_vector(scenario.project.id, scenario.stage)
    profile = load_profile(PACK_ROOT)
    observed = tmp_path / 'observations.jsonl'
    executor = ExactDynamicVectorExecutor(
        {**vector, 'schema_documents': profile['schemaDocuments']}, observed, profile['inputSchema'],
    )
    value = dynamic_input(vector['cases'][0]['input_template'], '71000000-0000-4000-8000-000000000001')
    value['binding']['stable_id'] = '999'
    with pytest.raises(ValueError):
        asyncio.run(executor.execute(SimpleNamespace(messages=(('user', canonical_bytes(value).decode()),),
                                                     effective_input_sha256='a' * 64)))
    assert not observed.exists()
    value = dynamic_input(vector['cases'][0]['input_template'], '71000000-0000-4000-8000-000000000001')
    value['evidence'][0]['value']['summary'] = 'Changed fixture value'
    value['evidence'][0]['source_hash'] = content_hash(value['evidence'][0]['value'])
    with pytest.raises(ValueError):
        asyncio.run(executor.execute(SimpleNamespace(messages=(('user', canonical_bytes(value).decode()),),
                                                     effective_input_sha256='a' * 64)))
    assert not observed.exists()


def test_shouldKeepWeekTransportBoundToExactPopulationAndPagination(tmp_path):
    module, _ = fixture()
    data = importlib.import_module('scripts.validation.project_week_data')
    transport = module.WeekJiraHttpAdapter(SimpleNamespace(), tmp_path / 'requests.jsonl')
    assert transport._allowed('/jira/rest/api/2/search', {
        'jql': data.WEEK_QUERY, 'validateQuery': 'true', 'startAt': '2', 'maxResults': '2',
        'fields': 'id,key,summary,updated,status,assignee,resolution,issuelinks',
    })
    assert transport._allowed('/jira/rest/api/2/issue/103', {'fields': '*all', 'expand': 'changelog,names,schema'})
    assert not transport._allowed('/jira/rest/api/2/issue/999', {'fields': '*all', 'expand': 'changelog,names,schema'})
    assert not transport._allowed('/jira/rest/api/2/search', {
        'jql': 'project = OTHER', 'validateQuery': 'true', 'startAt': '0', 'maxResults': '2',
        'fields': 'id,key,summary,updated,status,assignee,resolution,issuelinks',
    })


@pytest.mark.django_db(transaction=True)
def test_shouldCaptureThreeRealRowsMatchingTheRegisteredWeekVectors(tmp_path):
    module, _ = fixture()
    create_provider = module.create_week_provider
    from bug_metrics.app.api import ApiForBugTrend
    from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
    from project_management.app.api import ApiForProjectManagement, ProjectActor
    from project_management.app.domain.summary_delta import build_analysis_input
    from project_management.out.capture_archive import LocalArchiveRepositoryFactory
    from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog
    from project_management.services.capture import ProjectCaptureService
    from project_management.services.capture_archive import CaptureArchiveService
    from scripts.validation.project_full_stack_fixture import ACTOR_SUBJECT, archive_config, synthetic_profile_records
    from scripts.validation.project_week_data import WEEK_QUERY

    run = tmp_path / 'run'
    run.mkdir()
    (run / 'evidence').mkdir()
    catalog = module.prepare_catalog(run)
    api = ApiForProjectManagement(DashboardScopeCatalog(ApiForBugTrend(),
        lambda: ProjectProviderProfileRegistry.from_records(synthetic_profile_records(WEEK_QUERY))))
    root = tmp_path / 'archive'
    root.mkdir()
    archive = CaptureArchiveService(api, LocalArchiveRepositoryFactory(), archive_config(root))
    provider = create_provider(api, archive, run)
    receipt = ProjectCaptureService(api, provider.service, archive).capture(provider.context())
    actor = ProjectActor(ACTOR_SUBJECT)
    capture = archive.read_capture(actor, catalog['project_id'], catalog['stage_id'], receipt.capture_id)
    assert receipt.complete
    assert [row.identity.stable_id for row in capture.snapshots] == ['101', '102', '103']
    vector = json.loads((run / 'fixture-vector.json').read_text())
    from scripts.validation.project_full_stack_base import normalize_capture_id
    from project_management.app.domain.captures import SourceChainKey
    for reference, expected in zip(capture.snapshots, vector['cases']):
        key = SourceChainKey('jira', reference.identity.endpoint_id, reference.identity.stable_id,
                             'principal-1', provider.stage.definition_hash)
        source = archive.read_snapshot(actor, catalog['project_id'], catalog['stage_id'], receipt.capture_id, key)
        prepared = build_analysis_input(catalog['project_id'], provider.stage, key, (reference,), (source,),
                                        'project-reporting.summary@review-1')
        normalized = normalize_capture_id(json.loads(prepared.input_content), receipt.capture_id,
                                          vector['capture_placeholder'])
        assert normalized == expected['input_template']


def dynamic_input(template, capture_id):
    value = deepcopy(template)
    value['target_capture_id'] = capture_id
    value['delta']['to_capture_id'] = capture_id
    for record in value['evidence']:
        record['capture_id'] = capture_id
    return value
