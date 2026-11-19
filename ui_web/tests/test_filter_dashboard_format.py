import unittest
from datetime import datetime, timedelta, timezone

from django.utils.html import conditional_escape

from ui_web.templatetags.dashboard_format import (
    EMPTY_VALUE, age_seconds, iso_datetime, or_dash, provider_tag, series_label, split_csv, status_tag, status_tone,
    timestamp,
)


class TestDashboardFormatFilters(unittest.TestCase):

    def test_shouldRenderAwareIsoTextAsUtcMinuteLabel(self):
        self.assertEqual('2026-11-08 08:24 UTC', iso_datetime('2026-11-08T08:24:14.717328+00:00'))

    def test_shouldConvertOffsetTimestampToUtc(self):
        moment = datetime(2026, 8, 19, 9, 30, tzinfo=timezone(timedelta(hours=8)))

        self.assertEqual('2026-08-19 01:30 UTC', iso_datetime(moment))

    def test_shouldKeepDateOnlyAndUnparseableTextUnchanged(self):
        self.assertEqual('2026-08-03', iso_datetime('2026-08-03'))
        self.assertEqual('yesterday afternoon', iso_datetime('yesterday afternoon'))

    def test_shouldRenderTimeElementWithExactValueOrDashWhenEmpty(self):
        self.assertEqual(
            '<time datetime="2026-08-19T00:00:00+00:00" title="2026-08-19T00:00:00+00:00">2026-08-19 00:00 UTC</time>',
            timestamp('2026-08-19T00:00:00+00:00'),
        )
        self.assertEqual(EMPTY_VALUE, timestamp(''))

    def test_shouldMapMachineStatusesToTagTones(self):
        self.assertEqual('is-danger', status_tone('auth_failed'))
        self.assertEqual('is-warning', status_tone('stale_config'))
        self.assertEqual('', status_tone('not_configured'))
        self.assertEqual('', status_tone('unavailable'))
        self.assertEqual('is-success', status_tone('live_synced'))
        self.assertEqual('is-warning', status_tone('needs_metric_recipe'))
        self.assertEqual('is-success', status_tone('published'))
        self.assertEqual('', status_tone('materialized_from_seed_hsdes_facts'))

    def test_shouldRenderStatusTagOrDashWhenMissing(self):
        self.assertEqual('<span class="tag is-danger">auth_failed</span>', status_tag('auth_failed'))
        self.assertEqual('<span class="tag">not_configured</span>', status_tag('not_configured'))
        self.assertEqual(EMPTY_VALUE, status_tag(None))

    def test_shouldRenderProviderIdentityTagOrDashWhenMissing(self):
        self.assertEqual('<span class="tag scope-provider-tag is-provider-green">Jira</span>', provider_tag('jira'))
        self.assertEqual('<span class="tag scope-provider-tag is-provider-blue">HSD-ES</span>', provider_tag('hsdes'))
        self.assertEqual('<span class="tag scope-provider-tag is-provider-neutral">GITLAB</span>', provider_tag('gitlab'))
        self.assertEqual([EMPTY_VALUE, EMPTY_VALUE], [provider_tag(None), provider_tag(' ')])

    def test_shouldRenderCompactAges(self):
        self.assertEqual(['45s', '12m', '3h 5m', '2d 4h', EMPTY_VALUE], [
            age_seconds(45), age_seconds(720), age_seconds(11100), age_seconds(187200), age_seconds(''),
        ])

    def test_shouldRenderMissingValuesAsMutedDashAndKeepRealValues(self):
        self.assertEqual('<span class="has-text-grey-light">—</span>', or_dash(None))
        self.assertEqual(EMPTY_VALUE, or_dash('  '))
        self.assertEqual(0, or_dash(0))
        self.assertEqual('&lt;b&gt;', conditional_escape(or_dash('<b>')))

    def test_shouldSplitCommaJoinedIdentifiers(self):
        self.assertEqual(['open_bug_trend', 'closed_bug_trend'], split_csv('open_bug_trend, closed_bug_trend'))
        self.assertEqual([], split_csv(''))

    def test_shouldLabelSeriesLikeTheChartLegend(self):
        self.assertEqual('New Critical High', series_label('new_critical_high'))
        self.assertEqual('All Open Bugs, New Critical High', series_label('all_open_bugs, new_critical_high'))

    def test_shouldTrimTimestampLabelToDateForDenseTables(self):
        self.assertEqual(
            '<time datetime="2025-12-01T08:00:00+00:00" title="2025-12-01T08:00:00+00:00">2025-12-01</time>',
            timestamp('2025-12-01T08:00:00+00:00', 'date'),
        )
