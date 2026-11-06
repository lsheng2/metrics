import pytest

from ui_web.report_daily_forms import ReportDailyPreparationForm, ReportDailyReprepareForm


SERIES = '10000000-0000-4000-8000-000000000001'
CAPTURE = '10000000-0000-4000-8000-000000000002'
PUBLICATION = '10000000-0000-4000-8000-000000000003'
TEMPLATE = 'user|10000000-0000-4000-8000-000000000004|1|' + 'a' * 64


def payload():
    return {
        'command_id': '10000000-0000-4000-8000-000000000005',
        'series_id': SERIES,
        'meeting_date': '2026-11-02',
        'template_choice': TEMPLATE,
        'expected_series_policy_hash': 'b' * 64,
        'baseline_publication_id': '',
        'baseline_manifest_hash': '',
        'baseline_commit': '',
        'source_mode': 'saved_capture',
        'capture_id': CAPTURE,
        'analysis_mode': 'manual_only',
    }


def prepare_form(data):
    return ReportDailyPreparationForm(
        data,
        series_choices=((SERIES, 'Daily'),),
        template_choices=((TEMPLATE, 'Daily v1'),),
        capture_choices=((CAPTURE, 'Retained source'),),
    )


def test_shouldRequireDisplayedPolicyExpectationBeforeDailyPreparation():
    data = payload()
    del data['expected_series_policy_hash']

    assert not prepare_form(data).is_valid()


@pytest.mark.parametrize('form_kind', ('prepare', 'reprepare'))
@pytest.mark.parametrize('invalid', (
    {'baseline_publication_id': PUBLICATION},
    {'baseline_publication_id': 'not-a-publication', 'baseline_manifest_hash': 'c' * 64, 'baseline_commit': 'd' * 40},
    {'baseline_publication_id': PUBLICATION, 'baseline_manifest_hash': 'c' * 64, 'baseline_commit': 'z' * 40},
))
def test_shouldRejectMalformedBaselineAsFormErrorBeforeCallingService(form_kind, invalid):
    data = {**payload(), **invalid}
    if form_kind == 'prepare':
        form = prepare_form(data)
    else:
        data['preparation_id'] = '10000000-0000-4000-8000-000000000006'
        form = ReportDailyReprepareForm(data, template_choices=((TEMPLATE, 'Daily v1'),))

    assert not form.is_valid()


def test_shouldRetainExactValidDisplayedBaseline():
    data = {
        **payload(),
        'baseline_publication_id': PUBLICATION,
        'baseline_manifest_hash': 'c' * 64,
        'baseline_commit': 'd' * 40,
    }
    form = prepare_form(data)

    assert form.is_valid()
    assert form.expected_baseline_ref().publication_id == PUBLICATION
    assert form.expected_baseline_ref().commit == 'd' * 40


def test_shouldKeepReplaySyntaxValidWhenRuntimeIsUnavailable():
    form = ReportDailyPreparationForm(
        {**payload(), 'source_mode': 'refresh', 'capture_id': '', 'analysis_mode': 'changed_items'},
        series_choices=((SERIES, 'Daily'),),
        template_choices=((TEMPLATE, 'Daily v1'),),
        runtime_ready=False,
    )

    assert form.is_valid()
