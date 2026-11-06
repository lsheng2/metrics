from unittest.mock import patch

import pytest
from django.db import OperationalError
from django.test import TestCase

from project_management.app.api import ApiForProjectManagement
from project_management.app.api import reports as report_api
from project_management.app.api.report_factories import build_report_template_service
from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.contracts import ProjectActor, ProjectError
from project_management.app.domain.report_templates import payload_for_revision, validate_report_template_revision
from project_management.models import Project, ProjectAuditEvent
from project_management.models_report_templates import (
    ReportTemplate,
    ReportTemplateCommand,
    ReportTemplateRevisionRecord,
    ReportTemplateUsage,
    ReportTemplateUse,
)
from project_management.tests.fakes import FixedCatalog
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_report_template_compilation import matrix_block, schema1_document


def policy():
    return {'schema_version': 1, 'instructions': {'40000000-0000-4000-8000-000000000001': 'Fill from accepted source notes.'}}


def blank_document():
    return {'schema_version': 1, 'report_kind': 'daily', 'blocks': []}


class TestReportTemplateLibrary(TestCase):
    def setUp(self):
        self.actor = ProjectActor('author')
        self.other = ProjectActor('other')
        self.project_api = ApiForProjectManagement(FixedCatalog())
        self.project = self.project_api.create_project(self.actor, key='alpha', name='Alpha')
        self.other_project = self.project_api.create_project(self.other, key='other', name='Other')
        self.target_project = self.project_api.create_project(self.actor, key='beta', name='Beta')
        self.service = report_api.ReportTemplateService()

    def test_should_create_draft_then_ready_revision_and_preserve_revision_one(self):
        created = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1000),
            name='Daily draft', document=blank_document(), fill_policy={'schema_version': 1, 'instructions': {}},
        )
        ready = self.service.save(
            self.actor, self.project.id, str(created.template_id), command_id=draft_command(1001),
            expected_revision=1, expected_revision_hash=created.revision_hash,
            name='Daily ready', document=schema1_document(), fill_policy=policy(),
        )
        revision_one = self.service.get(self.actor, self.project.id, str(created.template_id), revision=1)
        replay = self.service.save(
            self.actor, self.project.id, str(created.template_id), command_id=draft_command(1001),
            expected_revision=1, expected_revision_hash=created.revision_hash,
            name='Daily ready', document=schema1_document(), fill_policy=policy(),
        )

        assert created.readiness == 'draft'
        assert ready.revision == 2
        assert ready.readiness == 'ready'
        assert revision_one.name == 'Daily draft'
        assert revision_one.revision_hash == created.revision_hash
        assert replay.revision_hash == ready.revision_hash
        assert ReportTemplateUsage.objects.get(project_id=self.project.id).revision_count == 2

    def test_should_reject_changed_replay_and_stale_revision_or_hash(self):
        created = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1010),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )

        with pytest.raises(report_api.ReportError) as changed:
            self.service.create(
                self.actor, self.project.id, command_id=draft_command(1010),
                name='Changed', document=schema1_document(), fill_policy=policy(),
            )
        with pytest.raises(report_api.ReportError) as stale_revision:
            self.service.save(
                self.actor, self.project.id, str(created.template_id), command_id=draft_command(1011),
                expected_revision=0, expected_revision_hash=created.revision_hash,
                name='Daily', document=schema1_document(), fill_policy=policy(),
            )
        with pytest.raises(report_api.ReportError) as stale_hash:
            self.service.archive(
                self.actor, self.project.id, str(created.template_id), command_id=draft_command(1012),
                expected_revision=1, expected_revision_hash='0' * 64,
            )

        assert changed.value.code == 'REPORT_REVISION_CONFLICT'
        assert stale_revision.value.code == 'REPORT_REVISION_CONFLICT'
        assert stale_hash.value.code == 'REPORT_REVISION_CONFLICT'
        assert ReportTemplateRevisionRecord.objects.count() == 1

    def test_should_reject_stored_revision_with_false_derived_hashes_even_when_payload_hash_matches(self):
        created = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1015),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        record = ReportTemplateRevisionRecord.objects.get(template_id=created.template_id, revision=1)
        payload = dict(record.payload_json)
        payload['presentation_hash'] = '0' * 64
        record.payload_json = payload
        record.payload_hash = sha256_bytes(canonical_bytes(payload))
        record.save(update_fields=['payload_json', 'payload_hash'])

        with pytest.raises(report_api.ReportError) as error:
            self.service.get(self.actor, self.project.id, str(created.template_id), revision=1)

        assert error.value.code == 'REPORT_ARTIFACT_INVALID'

    def test_should_refuse_archived_project_writes_without_head_usage_command_or_audit_change(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1016),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        Project.objects.filter(pk=self.project.id).update(archived=True)
        before = self._state()
        selection = report_api.UserTemplateSelection(str(ready.template_id), ready.revision, ready.revision_hash)

        attempts = (
            lambda: self.service.create(
                self.actor, self.project.id, command_id=draft_command(1017),
                name='New', document=schema1_document(), fill_policy=policy(),
            ),
            lambda: self.service.save(
                self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1018),
                expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
                name='Saved', document=schema1_document(), fill_policy=policy(),
            ),
            lambda: self.service.archive(
                self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1019),
                expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
            ),
            lambda: self.service.use(
                self.actor, self.project.id, command_id=draft_command(1021),
                draft_id='72000000-0000-4000-8000-000000000001', request_hash='6' * 64,
                selection=selection, use_mode='standalone',
            ),
            lambda: self.service.copy(
                self.actor, self.project.id, str(ready.template_id), revision=ready.revision,
                target_project_id=self.target_project.id, command_id=draft_command(1022), name='Copied',
            ),
        )

        for attempt in attempts:
            with pytest.raises(ProjectError) as error:
                attempt()
            assert error.value.code == 'PROJECT_ARCHIVED'
            assert self._state() == before

    def test_should_refuse_archived_template_save_without_mutation(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1023),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        self.service.archive(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1024),
            expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
        )
        before = self._state()

        with pytest.raises(report_api.ReportError) as error:
            self.service.save(
                self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1025),
                expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
                name='Archived save', document=schema1_document(), fill_policy=policy(),
            )

        assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'
        assert self._state() == before

    def test_should_reject_self_consistent_command_payload_that_no_longer_matches_revision_record(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1026),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        saved = self.service.save(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1027),
            expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
            name='Saved', document=schema1_document(), fill_policy=policy(),
        )
        command = ReportTemplateCommand.objects.get(command=draft_command(1027))
        payload = decode_json(canonical_bytes(command.payload_json))
        payload['revision_payload']['name'] = 'Tampered but self consistent'
        payload['revision_payload']['validation_codes'] = []
        payload['revision_payload']['readiness'] = 'ready'
        command.payload_json = payload
        command.payload_hash = sha256_bytes(canonical_bytes(payload))
        command.save(update_fields=['payload_json', 'payload_hash'])

        with pytest.raises(report_api.ReportError) as error:
            self.service.save(
                self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1027),
                expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
                name='Saved', document=schema1_document(), fill_policy=policy(),
            )

        assert error.value.code == 'REPORT_ARTIFACT_INVALID'
        assert self.service.get(self.actor, self.project.id, str(ready.template_id), revision=saved.revision).name == 'Saved'

    def test_should_reject_self_consistent_use_payload_or_use_record_tamper_on_replay(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1028),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        selection = report_api.UserTemplateSelection(str(ready.template_id), ready.revision, ready.revision_hash)
        self.service.use(
            self.actor, self.project.id, command_id=draft_command(1029),
            draft_id='73000000-0000-4000-8000-000000000001', request_hash='7' * 64,
            selection=selection, use_mode='standalone',
        )
        command = ReportTemplateCommand.objects.get(command=draft_command(1029))
        original_payload = decode_json(canonical_bytes(command.payload_json))
        tampered_payload = decode_json(canonical_bytes(original_payload))
        tampered_payload['use_payload']['template_snapshot']['resolved_document']['report_kind'] = 'weekly'
        command.payload_json = tampered_payload
        command.payload_hash = sha256_bytes(canonical_bytes(tampered_payload))
        command.save(update_fields=['payload_json', 'payload_hash'])

        with pytest.raises(report_api.ReportError) as command_error:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1029),
                draft_id='73000000-0000-4000-8000-000000000001', request_hash='7' * 64,
                selection=selection, use_mode='standalone',
            )

        command.payload_json = original_payload
        command.payload_hash = sha256_bytes(canonical_bytes(command.payload_json))
        command.save(update_fields=['payload_json', 'payload_hash'])
        use = ReportTemplateUse.objects.get(command=draft_command(1029))
        use.snapshot_json = tampered_payload['use_payload']
        use.snapshot_hash = sha256_bytes(canonical_bytes(use.snapshot_json))
        use.save(update_fields=['snapshot_json', 'snapshot_hash'])

        with pytest.raises(report_api.ReportError) as use_error:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1029),
                draft_id='73000000-0000-4000-8000-000000000001', request_hash='7' * 64,
                selection=selection, use_mode='standalone',
            )

        assert command_error.value.code == 'REPORT_ARTIFACT_INVALID'
        assert use_error.value.code == 'REPORT_ARTIFACT_INVALID'

    def test_should_reject_matching_command_and_use_payload_drift_from_revision_without_mutation(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1037),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        selection = report_api.UserTemplateSelection(str(ready.template_id), ready.revision, ready.revision_hash)
        self.service.use(
            self.actor, self.project.id, command_id=draft_command(1038),
            draft_id='74000000-0000-4000-8000-000000000001', request_hash='8' * 64,
            selection=selection, use_mode='standalone',
        )
        before = self._state()
        command = ReportTemplateCommand.objects.get(command=draft_command(1038))
        payload = decode_json(canonical_bytes(command.payload_json))
        payload['use_payload']['template_snapshot']['resolved_document']['report_kind'] = 'weekly'
        payload['use_payload']['template_definition']['template_hash'] = '0' * 64
        command.payload_json = payload
        command.payload_hash = sha256_bytes(canonical_bytes(payload))
        command.save(update_fields=['payload_json', 'payload_hash'])
        use = ReportTemplateUse.objects.get(command=draft_command(1038))
        use.snapshot_json = payload['use_payload']
        use.snapshot_hash = sha256_bytes(canonical_bytes(use.snapshot_json))
        use.save(update_fields=['snapshot_json', 'snapshot_hash'])

        with pytest.raises(report_api.ReportError) as error:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1038),
                draft_id='74000000-0000-4000-8000-000000000001', request_hash='8' * 64,
                selection=selection, use_mode='standalone',
            )

        assert error.value.code == 'REPORT_ARTIFACT_INVALID'
        assert self._state() == before

    def test_should_rollback_all_template_rows_when_audit_fails_before_commit(self):
        audit_count = ProjectAuditEvent.objects.count()
        with patch('project_management.services.report_templates.ProjectAuditEvent.objects.create',
                   side_effect=OperationalError('disk write failed')):
            with pytest.raises(OperationalError):
                self.service.create(
                    self.actor, self.project.id, command_id=draft_command(1020),
                    name='Rollback', document=schema1_document(), fill_policy=policy(),
                )

        assert ReportTemplate.objects.count() == 0
        assert ReportTemplateRevisionRecord.objects.count() == 0
        assert ReportTemplateCommand.objects.count() == 0
        assert ReportTemplateUsage.objects.count() == 0
        assert ProjectAuditEvent.objects.count() == audit_count

    def test_should_use_archive_and_replay_frozen_snapshot_without_dynamic_latest(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1030),
            name='Daily', document=schema1_document(), fill_policy=policy(),
        )
        selection = report_api.UserTemplateSelection(str(ready.template_id), ready.revision, ready.revision_hash)
        pinned = self.service.use(
            self.actor, self.project.id, command_id=draft_command(1031),
            draft_id='70000000-0000-4000-8000-000000000001', request_hash='1' * 64,
            selection=selection, use_mode='standalone',
        )
        self.service.archive(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1032),
            expected_revision=ready.revision, expected_revision_hash=ready.revision_hash,
        )
        after_archive = self.service.get(self.actor, self.project.id, str(ready.template_id), revision=1)
        replay = self.service.use(
            self.actor, self.project.id, command_id=draft_command(1031),
            draft_id='70000000-0000-4000-8000-000000000001', request_hash='1' * 64,
            selection=selection, use_mode='standalone',
        )

        with pytest.raises(report_api.ReportError) as new_use:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1033),
                draft_id='70000000-0000-4000-8000-000000000002', request_hash='2' * 64,
                selection=selection, use_mode='standalone',
            )

        assert after_archive.revision_hash == ready.revision_hash
        assert replay.template_snapshot == pinned.template_snapshot
        assert replay.template_definition.template_hash == ready.presentation_hash
        assert new_use.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'
        assert ReportTemplateUse.objects.count() == 1

    def test_should_replay_archive_as_frozen_original_summary_not_current_head(self):
        ready = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1034),
            name='Daily v1', document=schema1_document(), fill_policy=policy(),
        )
        saved = self.service.save(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1035),
            expected_revision=1, expected_revision_hash=ready.revision_hash,
            name='Daily v2', document=schema1_document(), fill_policy=policy(),
        )
        archived = self.service.archive(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1036),
            expected_revision=saved.revision, expected_revision_hash=saved.revision_hash,
        )
        template = ReportTemplate.objects.get(pk=ready.template_id)
        validated = validate_report_template_revision('Injected v3', schema1_document(), policy())
        payload = payload_for_revision(template.id, 3, self.project.id, self.actor.subject, '2026-11-04T00:00:00+00:00', validated)
        ReportTemplateRevisionRecord.objects.create(
            template=template, revision=3, payload_json=payload, payload_hash=sha256_bytes(canonical_bytes(payload)),
        )
        ReportTemplate.objects.filter(pk=template.id).update(current_revision=3)

        replay = self.service.archive(
            self.actor, self.project.id, str(ready.template_id), command_id=draft_command(1036),
            expected_revision=saved.revision, expected_revision_hash=saved.revision_hash,
        )

        assert archived.current_revision == 2
        assert archived.name == 'Daily v2'
        assert replay == archived

    def test_should_copy_between_owned_projects_with_new_ids_and_policy_remap(self):
        source = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1040),
            name='Copy source', document=schema1_document(), fill_policy=policy(),
        )

        with pytest.raises(ProjectError):
            self.service.copy(
                self.actor, self.other_project.id, str(source.template_id),
                revision=1, target_project_id=self.target_project.id,
                command_id=draft_command(1041), name='Refused',
            )
        copied = self.service.copy(
            self.actor, self.project.id, str(source.template_id),
            revision=1, target_project_id=self.target_project.id,
            command_id=draft_command(1042), name='Copied',
        )

        source_slot = source.document['blocks'][1]['slot_id']
        copied_slot = copied.document['blocks'][1]['slot_id']
        assert copied.template_id != source.template_id
        assert copied_slot != source_slot
        assert source_slot in source.fill_policy['instructions']
        assert copied_slot in copied.fill_policy['instructions']
        assert source_slot not in copied.fill_policy['instructions']

    def test_should_allow_v1_standalone_use_and_fail_closed_for_v2_matrix_context(self):
        v1 = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1050),
            name='V1', document=schema1_document(), fill_policy=policy(),
        )
        v2_missing_doc = schema1_document()
        v2_missing_doc['schema_version'] = 2
        v2_ready_doc = dict(v2_missing_doc)
        v2_ready_doc['blocks'] = [*v2_missing_doc['blocks'], matrix_block()]
        missing = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1051),
            name='Missing matrix', document=v2_missing_doc,
            fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
        )
        matrix = self.service.create(
            self.actor, self.project.id, command_id=draft_command(1052),
            name='Matrix', document=v2_ready_doc,
            fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
        )

        pinned = self.service.use(
            self.actor, self.project.id, command_id=draft_command(1053),
            draft_id='71000000-0000-4000-8000-000000000001', request_hash='3' * 64,
            selection=report_api.UserTemplateSelection(str(v1.template_id), 1, v1.revision_hash),
            use_mode='standalone',
        )
        with pytest.raises(report_api.ReportError) as not_ready:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1054),
                draft_id='71000000-0000-4000-8000-000000000002', request_hash='4' * 64,
                selection=report_api.UserTemplateSelection(str(missing.template_id), 1, missing.revision_hash),
                use_mode='standalone',
            )
        with pytest.raises(report_api.ReportError) as context:
            self.service.use(
                self.actor, self.project.id, command_id=draft_command(1055),
                draft_id='71000000-0000-4000-8000-000000000003', request_hash='5' * 64,
                selection=report_api.UserTemplateSelection(str(matrix.template_id), 1, matrix.revision_hash),
                use_mode='standalone',
            )

        assert pinned.template_snapshot['renderer_version'] == 'template-document/1'
        assert missing.readiness == 'draft'
        assert matrix.readiness == 'ready'
        assert not_ready.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'
        assert context.value.code == 'REPORT_CONTEXT_REQUIRED'

    def test_should_enforce_quotas_and_report_busy_without_mutation(self):
        limited = report_api.ReportTemplateService(report_api.ReportTemplateLimits(max_templates=1, max_revisions=1))
        first = limited.create(
            self.actor, self.project.id, command_id=draft_command(1060),
            name='One', document=schema1_document(), fill_policy=policy(),
        )

        with pytest.raises(report_api.ReportError) as too_many_templates:
            limited.create(
                self.actor, self.project.id, command_id=draft_command(1061),
                name='Two', document=schema1_document(), fill_policy=policy(),
            )
        with pytest.raises(report_api.ReportError) as too_many_revisions:
            limited.save(
                self.actor, self.project.id, str(first.template_id), command_id=draft_command(1062),
                expected_revision=1, expected_revision_hash=first.revision_hash,
                name='One again', document=schema1_document(), fill_policy=policy(),
            )
        with patch('project_management.services.report_templates.Project.objects.filter',
                   side_effect=OperationalError('database is locked')):
            with pytest.raises(ProjectError) as busy:
                self.service.archive(
                    self.actor, self.project.id, str(first.template_id), command_id=draft_command(1063),
                    expected_revision=1, expected_revision_hash=first.revision_hash,
                )

        assert too_many_templates.value.code == 'REPORT_LIMIT'
        assert too_many_revisions.value.code == 'REPORT_LIMIT'
        assert busy.value.code == 'PROJECT_BUSY'
        assert Project.objects.get(pk=self.project.id).archived is False

    def test_should_reject_unbounded_library_list_limit(self):
        with pytest.raises(report_api.ReportError) as error:
            self.service.list(self.actor, self.project.id, limit=101)

        assert error.value.code == 'REPORT_LIMIT'

    def test_public_factory_should_build_library_without_report_renderer_or_model_client(self):
        service = build_report_template_service()

        assert isinstance(service, report_api.ReportTemplateService)

    def _state(self):
        usage = ReportTemplateUsage.objects.filter(project_id=self.project.id).first()
        return {
            'project_revision': Project.objects.get(pk=self.project.id).revision,
            'template_count': ReportTemplate.objects.filter(project_id=self.project.id).count(),
            'revision_count': ReportTemplateRevisionRecord.objects.filter(template__project_id=self.project.id).count(),
            'command_count': ReportTemplateCommand.objects.filter(project_id=self.project.id).count(),
            'use_count': ReportTemplateUse.objects.filter(project_id=self.project.id).count(),
            'audit_count': ProjectAuditEvent.objects.filter(project_id=self.project.id).count(),
            'usage': None if usage is None else (usage.retained_payload_bytes, usage.template_count, usage.revision_count),
            'heads': tuple(ReportTemplate.objects.filter(project_id=self.project.id).order_by('id').values_list('id', 'current_revision', 'archived')),
        }
