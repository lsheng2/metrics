import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_meetings import local_dates, meeting_request
from project_management.tests.test_report_history_composer_fix2 import context, matrix_options, snapshot


@pytest.mark.parametrize('start,end,count', [
    ('2026-11-03', '2026-11-03', 1),
    ('2026-11-03', '2026-11-05', 3),
    ('2026-11-09', '2026-11-15', 7),
    ('2026-11-09', '2026-11-22', 14),
    ('2026-12-28', '2027-01-10', 14),
])
def test_literal_gap_dates_do_not_require_intermediate_reports(start, end, count):
    dates = local_dates(start, end)
    assert len(dates) == count
    assert dates[0] == start
    assert dates[-1] == end


@pytest.mark.parametrize('field,value', [
    ('expected_revision', True), ('expected_revision', -1),
    ('action', []), ('action', 'finalize'),
    ('from_date', '2026-02-30'), ('from_date', '20261109'),
    ('through_date', '2026-11-08'), ('through_date', '2027-02-01'),
    ('reason', 'A\nB'), ('reason', '\x7f'), ('reason', 'x' * 241),
])
def test_bad_change_shapes_return_domain_errors(field, value):
    request = {
        'expected_revision': 0, 'expected_revision_hash': 'a' * 64,
        'expected_series_policy_hash': 'b' * 64, 'action': 'skip',
        'from_date': '2026-11-09', 'through_date': '2026-11-22', 'reason': '',
    }
    request[field] = value
    with pytest.raises(report_api.ReportError):
        meeting_request(**request)


@pytest.mark.parametrize('day', ['2026-11-06', '2026-11-09', '2026-11-16', '2026-11-23', '2027-01-04'])
def test_rollover_selects_actual_prior_note_not_previous_calendar_day(day):
    source = snapshot()
    previous = context(source, '2026-11-02')
    calendar = report_api.ReportingCalendar('intel-workweek', 7, 'Asia/Shanghai', 'iso8601', {})
    resumed = report_api.build_daily_authoring_context(
        series_id=previous['series_id'], series_policy_revision=previous['series_policy_revision'],
        series_policy_hash=previous['series_policy_hash'],
        meeting=report_api.meeting_identity(calendar, day), source_snapshot=source,
        matrix_options=matrix_options(),
        baseline_context=previous,
    )
    assert {note['meeting']['local_date'] for note in resumed['notes']} == {'2026-11-02'}
    assert {note['note_id']: note['body_hash'] for note in resumed['notes']} == {
        note['note_id']: note['body_hash'] for note in previous['notes']
    }
    assert resumed['actions'] == previous['actions']
