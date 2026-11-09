import unittest
from datetime import date

from ui_web.data.velocity_report_data import VelocityReportData
from ui_web.utils.velocity_summary_utils import VelocitySummaryUtils


class TestVelocitySummaryUtils(unittest.TestCase):

    def test_shouldSummarizeLatestPeriodsWhenReportsAreUnordered(self):
        # Given
        reports = [
            VelocityReportData(start_date=date(2026, 3, 1), velocity=1.5, story_points=30.0),
            VelocityReportData(start_date=date(2026, 1, 1), velocity=9.0, story_points=90.0),
            VelocityReportData(start_date=date(2026, 2, 1), velocity=2.5, story_points=20.0),
            VelocityReportData(start_date=date(2026, 4, 1), velocity=2.0, story_points=10.0),
        ]

        # When
        summary = VelocitySummaryUtils.summarize(reports, 3)

        # Then
        self.assertEqual(3, summary.period_count)
        self.assertAlmostEqual(2.0, summary.average_velocity)
        self.assertEqual('2026-04', summary.latest_period)
        self.assertEqual(2.0, summary.latest_velocity)
        self.assertAlmostEqual(0.5, summary.latest_change)
        self.assertEqual(60.0, summary.total_story_points)
        self.assertEqual('2026-02', summary.best_period)
        self.assertEqual(2.5, summary.best_velocity)

    def test_shouldOmitChangeWhenOnlyOnePeriodExists(self):
        # Given
        reports = [VelocityReportData(start_date=date(2026, 5, 1), velocity=3.0, story_points=12.0)]

        # When
        summary = VelocitySummaryUtils.summarize(reports, 12)

        # Then
        self.assertIsNone(summary.latest_change)
        self.assertEqual('2026-05', summary.best_period)

    def test_shouldReturnNoneWhenNoReportsExist(self):
        # When
        summary = VelocitySummaryUtils.summarize([], 12)

        # Then
        self.assertIsNone(summary)


if __name__ == '__main__':
    unittest.main()
