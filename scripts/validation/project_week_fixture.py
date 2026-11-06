import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from bug_metrics.provider_connections.normalization import endpoint_identifier
from project_management.app.api.capture_archive import (
    CaptureCoverage, PartCoverage, SnapshotInput, SourceChainKey, StoredSnapshotRef, WorkItemIdentity,
)
from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.summary_input import build_initial_input
from provider_sync.tests.capture_gateway_fixtures import comment, issue
from scripts.validation.project_full_stack_fixture import (
    ACTOR_SUBJECT, CAPTURE_PLACEHOLDER, ENDPOINT, PROFILE_REVISION, StrictJiraHttpAdapter,
    _current_ids, build_runtime_environment, expected_output, synthetic_profile_records,
)
from scripts.validation.project_week_data import WEEK_ITEMS, WEEK_QUERY


def prepare_catalog(run_dir):
    from scripts.validation.project_full_stack_fixture import prepare_catalog as original

    return original(run_dir, query=WEEK_QUERY, vector_builder=build_week_vector)


def build_week_runtime(connection, run_dir):
    from django.conf import settings
    from project_management.services.report_completion import ReportCompletionService
    from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
    from project_management.storage.report_reference_admission import CompletionAdmissionStore
    from ui_web.views.report_completion import ReportDraftCompletionView

    runtime = build_runtime_environment(
        connection, records=synthetic_profile_records(WEEK_QUERY),
        provider_factory=lambda api, archive: create_week_provider(api, archive, run_dir),
    )
    service = runtime.run_service
    verifier = ReferenceReceiptVerifier(settings.SECRET_KEY)
    completion = ReportCompletionService(
        service.draft_service, service.draft_service.source_reader,
        WeekReferenceReader(Path(run_dir) / 'evidence/reference-requests.jsonl'),
        verifier, CompletionAdmissionStore(service.archive.config.root),
    )
    ReportDraftCompletionView.completion_factory = staticmethod(lambda: completion)
    ReportDraftCompletionView.project_api_factory = staticmethod(lambda: service.project_api)
    return runtime


def create_week_provider(project_api, archive, run_dir):
    from project_management.app.api import ProjectActor
    from provider_sync.app.api.access import ProviderAccessService
    from provider_sync.out.jira_capture import JiraCaptureAdapter
    from provider_sync.tests.capture_gateway_fixtures import JiraFixture

    detail = project_api.get_project(ProjectActor(ACTOR_SUBJECT), _current_ids(project_api)[0])
    stage = next(item for item in detail.stages if item.source_status == 'current')
    sample = SimpleNamespace(actor=ProjectActor(ACTOR_SUBJECT), project=detail.project, stage=stage)
    fixture = JiraFixture(sample, archive=archive, query=WEEK_QUERY)
    fixture.project_api = project_api
    fixture.rows, fixture.comments = week_issues(), week_comments()
    fixture.transport = WeekJiraHttpAdapter(fixture, Path(run_dir) / 'evidence/provider-requests.jsonl')
    fixture.service = ProviderAccessService(project_api, fixture.resolver, {'jira': JiraCaptureAdapter()},
                                            archive, reader_factory=fixture.reader_factory,
                                            profile_registry=fixture.registry)
    return fixture


class WeekJiraHttpAdapter(StrictJiraHttpAdapter):
    def __init__(self, fixture, transcript):
        super().__init__(fixture)
        self.path = transcript

    def send(self, request, **kwargs):
        response = super().send(request, **kwargs)
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(self.transcript[-1], sort_keys=True) + '\n')
        return response

    def _allowed(self, path, params):
        if path == '/jira/rest/api/2/myself':
            return params == {}
        if path == '/jira/rest/api/2/search':
            if params == {'jql': WEEK_QUERY, 'validateQuery': 'true', 'startAt': '0', 'maxResults': '0', 'fields': 'id'}:
                return True
            return params in [
                {'jql': WEEK_QUERY, 'validateQuery': 'true', 'startAt': start, 'maxResults': '2',
                 'fields': 'id,key,summary,updated,status,assignee,resolution,issuelinks'}
                for start in ('0', '2')
            ]
        ids = {item[0] for item in WEEK_ITEMS}
        for identifier in ids:
            if path == f'/jira/rest/api/2/issue/{identifier}':
                return params == {'fields': '*all', 'expand': 'changelog,names,schema'}
            if path == f'/jira/rest/api/2/issue/{identifier}/comment':
                return params in ({'startAt': '0', 'maxResults': '2'}, {'startAt': '2', 'maxResults': '2'})
        return False


class WeekReferenceReader:
    def __init__(self, transcript):
        self.path = transcript

    def supports(self, stage, principal_id):
        return stage.descriptor.query == WEEK_QUERY and principal_id == 'principal-1'

    def read(self, context, member):
        from project_management.app.domain.report_completion import ReferenceObservation

        row = next((item for item in week_issues() if item['id'] == member.stable_id), None)
        if row is None:
            raise AssertionError('Reference is not in the fixed qualification population.')
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'stable_id': member.stable_id, 'scope_hash': context['membership_proof_hash']}) + '\n')
        return ReferenceObservation(
            identity={'provider_id': member.provider_id, 'endpoint_id': member.endpoint_id,
                      'stable_id': member.stable_id, 'display_key': member.display_key},
            requested_key=member.display_key, current_key=member.display_key,
            canonical_url=f'{ENDPOINT}/browse/{row["key"]}', title=row['fields']['summary'],
            assignee={'id': row['fields']['assignee']['key'], 'display_name': row['fields']['assignee']['displayName']},
            assignee_state='assigned', observed_at=datetime.now(UTC).isoformat(),
            source_updated_at='2026-11-01T01:00:00+00:00', lookup_kind='live',
            scope_snapshot_hash=context['membership_proof_hash'],
        )


def week_issues():
    return [
        issue(number, status=status, summary=title,
              assignee={'key': owner_id, 'displayName': owner_name},
              reporter={'key': 'qa-b', 'displayName': 'Bob'},
              resolution={'name': 'Fixed'} if status == 'Fixed' else None,
              description='Shared change PR-SYNTH-7; keep independent ticket rows.')
        for number, status, title, owner_id, owner_name in WEEK_ITEMS
    ]


def week_comments():
    return [
        comment(201, 'Track the independent issue against shared change PR-SYNTH-7.'),
        comment(202, 'The source record stays unchanged across the simulated meeting dates.'),
        comment(203, 'Bob (qa-b), please rerun validation on build r8.'),
    ]


def build_week_vector(project_id, stage):
    cases = [build_case(project_id, stage, row) for row in week_issues()]
    return {'schema_version': 2, 'scope_key': f'projects.{project_id}.stages.{stage.id}',
            'capture_placeholder': CAPTURE_PLACEHOLDER, 'cases': cases}


def build_case(project_id, stage, row):
    site = endpoint_identifier('jira', ENDPOINT, 'server_pat')
    identity = WorkItemIdentity('jira', site, row['id'], row['key'])
    fields, comments = row['fields'], week_comments()
    snapshot = SnapshotInput(
        identity, fields, {item['id']: item for item in comments}, {}, {}, {},
        CaptureCoverage(
            PartCoverage('complete', content_hash(fields), 1, 1, None),
            PartCoverage('complete', content_hash(comments), len(comments), len(comments), None),
            PartCoverage('complete', content_hash([]), 0, 0, None),
            PartCoverage('not_requested', None, 0, 0, 'BODY_NOT_REQUESTED'),
            PartCoverage('not_requested', None, 0, 0, 'BODY_NOT_REQUESTED'),
        ), (), True,
    )
    source_hash = content_hash({
        'identity': identity, 'facts': fields, 'comments_by_id': snapshot.comments_by_id,
        'history_by_id': {}, 'attachments_by_id': {}, 'dependencies_by_id': {},
    })
    reference = StoredSnapshotRef(identity, CAPTURE_PLACEHOLDER, 1, None, source_hash,
                                  f'captures/{CAPTURE_PLACEHOLDER}/snapshots/{source_hash}.json')
    key = SourceChainKey('jira', site, row['id'], 'principal-1', stage.definition_hash)
    prepared = build_initial_input(project_id, stage, key, reference, snapshot, PROFILE_REVISION)
    value = json.loads(prepared.input_content)
    output = expected_output(value)
    output['what'] = fields['summary'] + '.'
    output['current_position'] = f"The item is marked {fields['status']['name']}. Validation follow-up remains open."
    return {'capture_placeholder': CAPTURE_PLACEHOLDER, 'input_template': value,
            'input_template_sha256': prepared.input_hash, 'output_template': output}
