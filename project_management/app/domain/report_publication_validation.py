from dataclasses import dataclass

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.report_authoring import validate_template_snapshot
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import bytes_hash, read_json, revision_from_mapping, snapshot_from_mapping
from project_management.app.domain.report_draft_values import template_definition_from_mapping
from project_management.app.domain.report_publication_contracts import (
    MANIFEST_HASHED_FILES,
    PUBLICATION_FILES,
    manifest_from_mapping,
    manifest_payload,
    publication_id_for,
)


@dataclass(frozen=True, slots=True)
class PublicationValidationContext:
    project_id: str
    stage_id: str
    owner_subject: str
    rule_hash: str


def validate_publication_files(publication_id: str, files, context: PublicationValidationContext,
                               actor_subject: str | None = None, *, decode_revision=None):
    if set(files.keys()) != set(PUBLICATION_FILES):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    manifest_bytes = files['manifest.json']
    manifest_hash = bytes_hash(manifest_bytes)
    manifest = manifest_from_mapping(read_json(manifest_bytes))
    if manifest.publication_id != publication_id or canonical_bytes(manifest_payload(manifest)) != manifest_bytes:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if actor_subject is not None and manifest.finalized_by != actor_subject:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if publication_id_for(manifest.draft_id, manifest.draft_revision, manifest.purpose) != publication_id:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    for name in MANIFEST_HASHED_FILES:
        if bytes_hash(files[name]) != manifest.file_hashes[name]:
            raise ReportError('REPORT_ARTIFACT_INVALID')
    _verify_snapshot(manifest, files['snapshot.json'], context)
    template = _verify_template(manifest, files['template.json'])
    _verify_edits(manifest, files['edits.json'], template, decode_revision or revision_from_mapping)
    return manifest, manifest_hash


def _verify_snapshot(manifest, data, context):
    snapshot = snapshot_from_mapping(read_json(data))
    if (canonical_bytes(snapshot) != data or bytes_hash(data) != manifest.snapshot_hash
            or snapshot.project_id != context.project_id or snapshot.stage_id != context.stage_id
            or snapshot.owner_subject != context.owner_subject or snapshot.rule_hash != context.rule_hash
            or snapshot.source_as_of != manifest.source_as_of
            or snapshot.baseline_publication_id != manifest.baseline_publication_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _verify_template(manifest, data):
    if manifest.schema_version == 2:
        value = validate_template_snapshot(read_json(data))
        if (bytes_hash(data) != manifest.template_snapshot_hash
                or bytes_hash(canonical_bytes(value['resolved_document'])) != manifest.template_document_hash
                or value['fill_policy_hash'] != manifest.fill_policy_hash
                or value['presentation_hash'] != manifest.template_hash):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return value
    value = read_json(data)
    if set(value.keys()) != {'selection', 'definition'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    definition = template_definition_from_mapping(value['definition'])
    if definition.template_hash != manifest.template_hash:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return value


def _verify_edits(manifest, data, template, decode_revision):
    value = read_json(data)
    if manifest.schema_version == 2:
        _verify_schema2_edits(manifest, data, value, template, decode_revision)
        return
    if (not isinstance(value, dict) or value.get('schema_version') != 1
            or value.get('draft_id') != manifest.draft_id
            or value.get('selected_revision') != manifest.draft_revision
            or value.get('selected_revision_hash') != manifest.draft_revision_hash):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _verify_schema2_edits(manifest, data, value, template, decode_revision):
    expected = {'schema_version', 'draft_id', 'selected_revision', 'selected_revision_hash', 'revisions', 'authoring_context'}
    if (not isinstance(value, dict) or set(value.keys()) != expected or value['schema_version'] != 2
            or value['draft_id'] != manifest.draft_id
            or value['selected_revision'] != manifest.draft_revision
            or value['selected_revision_hash'] != manifest.draft_revision_hash
            or bytes_hash(data) != manifest.edits_hash):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    context = _verify_authoring_context(manifest, value['authoring_context'])
    revisions = value['revisions']
    if not isinstance(revisions, list) or len(revisions) != manifest.draft_revision:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    selected = None
    selected_hash = None
    for index, item in enumerate(revisions, 1):
        payload = _history_payload(item, index, manifest, decode_revision)
        if index == manifest.draft_revision:
            selected = payload
            selected_hash = item['revision_hash']
    if selected is None:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    if (selected['revision'] != manifest.draft_revision
            or selected_hash != manifest.draft_revision_hash
            or selected['template_definition'].template_hash != manifest.template_hash
            or selected['template_snapshot'] != template
            or selected['authoring_context'] != context):
        raise ReportError('REPORT_ARTIFACT_INVALID')


def _verify_authoring_context(manifest, context):
    if manifest.report_role == 'standalone':
        if context is not None or manifest.continuity_hash is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return None
    if manifest.report_role == 'daily':
        context = validate_daily_authoring_context(context, series_id=manifest.series_id)
        if manifest.continuity_hash != bytes_hash(canonical_bytes(context)):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        meeting = context['meeting']
        period = context['period']
        if (manifest.meeting_key != f"{meeting['calendar_id']}:{meeting['calendar_revision']}:{meeting['local_date']}"
                or manifest.period_key != f"{period['calendar_id']}:{period['calendar_revision']}:{period['workweek_year']}:ww{period['workweek']}"):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return context
    if manifest.report_role == 'weekly_view':
        context = validate_daily_authoring_context(context, series_id=manifest.series_id)
        if (context['meeting'] is not None or manifest.meeting_key is not None
                or manifest.continuity_hash != bytes_hash(canonical_bytes(context))):
            raise ReportError('REPORT_ARTIFACT_INVALID')
        period = context['period']
        if manifest.period_key != f"{period['calendar_id']}:{period['calendar_revision']}:{period['workweek_year']}:ww{period['workweek']}":
            raise ReportError('REPORT_ARTIFACT_INVALID')
        return context
    raise ReportError('REPORT_ARTIFACT_INVALID')


def _history_payload(item, index, manifest, decode_revision):
    if not isinstance(item, dict) or set(item.keys()) != {'revision', 'revision_hash', 'payload'}:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    payload = decode_revision(item['payload'])
    if (item['revision'] != index or payload['revision'] != index
            or item['revision_hash'] != bytes_hash(canonical_bytes(payload))
            or payload['draft_id'] != manifest.draft_id
            or payload['snapshot_hash'] != manifest.snapshot_hash
            or payload['selection'].purpose != manifest.purpose
            or payload['selection'].baseline_publication_id != manifest.baseline_publication_id
            or payload['selection'].parent_publication_id != manifest.parent_publication_id
            or payload['parent_publication_id'] != manifest.parent_publication_id):
        raise ReportError('REPORT_ARTIFACT_INVALID')
    return payload
