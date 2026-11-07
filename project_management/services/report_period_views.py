from project_management.app.domain.capture_values import decode_json
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.app.domain.report_continuity import PeriodView
from project_management.app.domain.report_meeting_matrix import build_meeting_matrix
from project_management.services.report_daily_baseline import select_daily_head
from project_management.services.report_publication_reads import ReportPublicationReader
from project_management.app.domain.report_publication_contracts import publication_path
from project_management.app.domain.report_observation_history import all_observations, known_meetings, upgrade_context


def read_period_view(archive, actor, project_id, stage_id, *, series_id, period_key, selected_publication_refs):
    refs = tuple(selected_publication_refs or ())
    if not refs:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    if len({(ref.publication_id, ref.manifest_hash, ref.commit) for ref in refs}) != len(refs):
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    with archive._report_repository(actor, project_id, stage_id, write=False) as repository:
        reader = ReportPublicationReader(repository)
        publications = tuple(sorted(
            (_publication(reader, ref, series_id, period_key) for ref in refs),
            key=lambda item: item.manifest.meeting_key,
        ))
        _reject_same_day(publications)
        head = select_daily_head(publications)
        _, source_snapshot = reader.snapshot(head.manifest.publication_id)
        context = _weekly_context(repository, publications)
        sorted_refs = tuple(_ref_for_publication(refs, publication) for publication in publications)
        return PeriodView(series_id, period_key, sorted_refs, source_snapshot, context, build_meeting_matrix(source_snapshot, context))


def _publication(reader, ref, series_id, period_key):
    publication = reader.get(ref.publication_id)
    manifest = publication.manifest
    if (publication.manifest_sha256 != ref.manifest_hash or publication.commit_id != ref.commit
            or manifest.schema_version != 2 or manifest.report_role != 'daily'
            or manifest.series_id != series_id or manifest.period_key != period_key):
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    return publication


def _weekly_context(repository, publications):
    pairs = tuple((publication, _publication_context(repository, publication)) for publication in publications)
    contexts = tuple(context['selected'] for _, context in pairs)
    context = contexts[-1]
    notes = _merge_notes(tuple((publication, item['selected']) for publication, item in pairs))
    actions = _merge_revised_records(tuple(item for _, item in pairs), 'actions', 'action_id')
    persistent_notes = _merge_revised_records(tuple(item for _, item in pairs), 'persistent_notes', 'note_id')
    if any(item['schema_version'] == 3 for item in contexts):
        context = upgrade_context(context)
    history = {}
    if context['schema_version'] == 3:
        meetings = {item['meeting']['local_date']: item for value in contexts for item in known_meetings(value)}
        reviews = {}
        for value in contexts:
            for item in value.get('meeting_reviews', ()):
                key = tuple(item['issue_ref'][field] for field in ('provider_id', 'endpoint_fingerprint', 'stable_id'))
                reviews[(key, item['meeting']['local_date'])] = item
        history = {'past_observations': (), 'meeting_history': tuple(meetings[key] for key in sorted(meetings)),
                   'meeting_reviews': tuple(reviews.values())}
    return validate_daily_authoring_context({
        **context,
        'report_role': 'weekly_view',
        'meeting': None,
        'weekly_seed': _merge_weekly_seed(context, actions),
        'notes': notes,
        'actions': actions,
        'persistent_notes': persistent_notes,
        'current_observations': _merge_observations(contexts),
        'selected_daily_publications': tuple(_publication_ref(publication) for publication, _ in pairs),
        **history,
    })


def _publication_context(repository, publication):
    edits = decode_json(repository.read_file(publication_path(publication.manifest.publication_id, 'edits.json'), publication.commit_id))
    context = edits.get('authoring_context')
    if context is None:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    selected = _revision_context(edits.get('revisions'), edits.get('selected_revision'))
    if selected != context:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    return {
        'initial': _revision_context(edits.get('revisions'), 1),
        'selected': selected,
    }


def _revision_context(revisions, revision):
    if type(revisions) is not list or type(revision) is not int:
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    for item in revisions:
        if type(item) is not dict or item.get('revision') != revision:
            continue
        payload = item.get('payload')
        if type(payload) is not dict or payload.get('authoring_context') is None:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        return payload['authoring_context']
    raise ReportError('REPORT_HISTORY_UNAVAILABLE')


def _reject_same_day(publications):
    seen = set()
    for publication in publications:
        key = publication.manifest.meeting_key
        if key in seen:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        seen.add(key)


def _merge_records(contexts, field, identity):
    values = {}
    for context in contexts:
        for item in context[field]:
            values[item[identity]] = item
    return tuple(values[key] for key in sorted(values))


def _merge_revised_records(contexts, field, identity):
    order = []
    values = {}
    for context in contexts:
        initial = _records_by_identity(context['initial'], field, identity)
        selected = _records_by_identity(context['selected'], field, identity)
        for key, item in selected.items():
            if key not in values:
                order.append(key)
                values[key] = item
            elif key not in initial:
                values[key] = item
            elif item != initial[key]:
                values[key] = _apply_selected_changes(values[key], initial[key], item)
    return tuple(values[key] for key in order)


def _records_by_identity(context, field, identity):
    records = {}
    for item in context[field]:
        key = item[identity]
        if key in records:
            raise ReportError('REPORT_HISTORY_UNAVAILABLE')
        records[key] = item
    return records


def _apply_selected_changes(current, initial, selected):
    if set(current) != set(initial) or set(initial) != set(selected):
        raise ReportError('REPORT_HISTORY_UNAVAILABLE')
    merged = dict(current)
    for key, value in selected.items():
        if value != initial[key]:
            merged[key] = value
    return merged


def _merge_weekly_seed(context, actions):
    return {
        **context['weekly_seed'],
        'unresolved_action_ids': tuple(
            action['action_id']
            for action in actions
            if action['tracking_state'] not in {'done', 'canceled'}
        ),
    }


def _merge_notes(pairs):
    selected_dates = {_publication_date(publication) for publication, _ in pairs}
    values = {}
    for publication, context in pairs:
        publication_date = _publication_date(publication)
        for note in context['notes']:
            note_date = note['meeting']['local_date']
            if note_date in selected_dates and note_date != publication_date:
                continue
            values[note['note_id']] = note
    return tuple(values[key] for key in sorted(values))


def _merge_actions(pairs):
    selected_dates = {_publication_date(publication) for publication, _ in pairs}
    values = {}
    for publication, context in pairs:
        publication_date = _publication_date(publication)
        for action in context['actions']:
            action_date = action['issued_meeting']['local_date']
            if action_date in selected_dates and action_date != publication_date:
                continue
            values[action['action_id']] = action
    return tuple(values[key] for key in sorted(values))


def _merge_observations(contexts):
    values = {}
    selected_dates = {context['meeting']['local_date'] for context in contexts if context['meeting']}
    for context in contexts:
        for item in all_observations(context):
            if (item['meeting']['local_date'] in selected_dates
                    and item['meeting']['local_date'] != context['meeting']['local_date']):
                continue
            key = (
                item['issue_ref']['provider_id'],
                item['issue_ref']['endpoint_fingerprint'],
                item['issue_ref']['stable_id'],
                item['meeting']['local_date'],
            )
            values[key] = item
    return tuple(values[key] for key in sorted(values))


def _publication_date(publication):
    return publication.manifest.meeting_key.split(':', 2)[2]


def _publication_ref(publication):
    return {
        'publication_id': publication.manifest.publication_id,
        'manifest_hash': publication.manifest_sha256,
        'commit': publication.commit_id,
    }


def _ref_for_publication(refs, publication):
    for ref in refs:
        if ref.publication_id == publication.manifest.publication_id:
            return ref
    raise ReportError('REPORT_HISTORY_UNAVAILABLE')
