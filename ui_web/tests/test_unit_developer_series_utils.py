import unittest

from ui_web.data.chart_data import ChartData, ChartDatasetData
from ui_web.utils.developer_series_utils import DeveloperSeriesUtils


def _chart(*developers):
    return ChartData(
        labels=['2026-09', '2026-10'],
        datasets=[ChartDatasetData(label=name, data=[1.0, 2.0]) for name in developers],
    )


class TestDeveloperSeriesUtils(unittest.TestCase):

    def test_shouldShowOnlySelectedDevelopersWithPaletteSlotsInDatasetOrder(self):
        # Given
        chart = _chart(*[f'dev{index}' for index in range(9)])

        # When
        series = DeveloperSeriesUtils.from_chart(chart, 'dev1, dev8,unknown')

        # Then
        self.assertEqual([f'dev{index}' for index in range(9)], [entry.name for entry in series])
        self.assertEqual([1, 2, 3, 4, 5, 6, 7, 8, 1], [entry.palette_slot for entry in series])
        self.assertEqual(['dev1', 'dev8'], [entry.name for entry in series if entry.shown])

    def test_shouldShowEveryoneWhenSelectionNamesNoChartedDeveloper(self):
        # Given
        chart = _chart('Ana', 'Ben')

        # When
        series = DeveloperSeriesUtils.from_chart(chart, 'Former Member')

        # Then
        self.assertTrue(all(entry.shown for entry in series))

    def test_shouldReturnNoSeriesWithoutChartData(self):
        # When / Then
        self.assertEqual([], DeveloperSeriesUtils.from_chart(None, ''))
        self.assertEqual([], DeveloperSeriesUtils.from_chart(ChartData(labels=[], datasets=[]), 'Ana'))
