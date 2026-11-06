from dataclasses import replace

from project_management.app.domain.report_completion import CompletionRequest, ReferenceObservation
from project_management.tests.report_draft_fixtures import StaticSourceReader


class SyntheticSourceReader(StaticSourceReader):
    def membership(self, actor, project_id, stage_id, snapshot):
        from project_management.services.report_membership import ScopeMember, ScopeMembershipSnapshot

        identity = replace(snapshot.rows[0].identity, stable_id='ALPHA-1', display_key='ALPHA-1')
        source_key = replace(snapshot.rows[0].source_key, stable_id='ALPHA-1')
        return ScopeMembershipSnapshot(
            schema_version=1,
            capture_id=snapshot.capture_id,
            source_commit=snapshot.source_commit,
            manifest_sha256='a' * 64,
            source_as_of=snapshot.source_as_of,
            rule_hash=snapshot.rule_hash,
            principal_id='principal:archive-owner',
            state='complete',
            observed_count=1,
            total_count=1,
            members=(ScopeMember(identity, source_key),),
            proof_hash='b' * 64,
        )


class SyntheticReferenceReader:
    def __init__(self, *, qualified=True, error=None):
        self.qualified = qualified
        self.error = error
        self.calls = []
        self.after_read = None

    def supports(self, stage, principal_id):
        return self.qualified

    def read(self, context, member):
        self.calls.append((context, member))
        if self.error:
            raise self.error
        if self.after_read is not None:
            self.after_read()
        return ReferenceObservation(
            identity={
                'provider_id': member.provider_id,
                'endpoint_id': member.endpoint_id,
                'stable_id': member.stable_id,
                'display_key': member.display_key,
            },
            requested_key=member.display_key,
            current_key=member.display_key,
            canonical_url='https://tracker.example.test/jira/browse/' + member.display_key,
            title='Synthetic provider title',
            assignee=None,
            assignee_state='unassigned',
            observed_at='2026-11-03T01:00:00+00:00',
            source_updated_at='2026-11-02T23:59:00+00:00',
            lookup_kind='live',
            scope_snapshot_hash='b' * 64,
        )


def completion_request(draft, token='#ALPHA-1', request_id='aaaaaaaa-aaaa-4aaa-8aaa-000000000001'):
    return CompletionRequest(
        request_id=request_id,
        token=token,
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        snapshot_hash=draft.snapshot_hash,
        region_target={'scope': 'report'},
        editor_epoch='epoch-1',
        local_version=1,
    )
