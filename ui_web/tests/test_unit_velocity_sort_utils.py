import unittest

from ui_web.data.chart_data import ChartData, ChartDatasetData
from ui_web.utils.velocity_sort_utils import VelocitySortUtils


class TestVelocitySortUtilsChronologicalSort(unittest.TestCase):

    def test_shouldSortLabelsChronologicallyWhenYearMonthFormatOutOfOrder(self):
        # Given
        chart = ChartData(
            labels=["2024-03", "2024-01", "2024-02"],
            datasets=[ChartDatasetData(label="Alice", data=[30.0, 10.0, 20.0])]
        )

        # When
        result = VelocitySortUtils.sort_chart_data_chronologically(chart)

        # Then
        self.assertEqual(result.labels, ["2024-01", "2024-02", "2024-03"])
        self.assertEqual(result.datasets[0].data, [10.0, 20.0, 30.0])

    def test_shouldSortAllDatasetValuesToMatchReorderedLabelsWhenMultipleDatasetsExist(self):
        # Given
        chart = ChartData(
            labels=["2024-12", "2024-10", "2024-11"],
            datasets=[
                ChartDatasetData(label="Alice", data=[12.0, 10.0, 11.0]),
                ChartDatasetData(label="Bob", data=[120.0, 100.0, 110.0])
            ]
        )

        # When
        result = VelocitySortUtils.sort_chart_data_chronologically(chart)

        # Then
        self.assertEqual(result.labels, ["2024-10", "2024-11", "2024-12"])
        self.assertEqual(result.datasets[0].data, [10.0, 11.0, 12.0])
        self.assertEqual(result.datasets[1].data, [100.0, 110.0, 120.0])

    def test_shouldFallBackToAlphabeticalSortWhenLabelsAreNotDateFormat(self):
        # Given
        chart = ChartData(
            labels=["Charlie", "Alice", "Bob"],
            datasets=[ChartDatasetData(label="Velocity", data=[3.0, 1.0, 2.0])]
        )

        # When
        result = VelocitySortUtils.sort_chart_data_chronologically(chart)

        # Then
        self.assertEqual(result.labels, ["Alice", "Bob", "Charlie"])
        self.assertEqual(result.datasets[0].data, [1.0, 2.0, 3.0])

    def test_shouldSortInDescendingOrderWhenAscendingIsFalse(self):
        # Given
        chart = ChartData(
            labels=["2024-01", "2024-03", "2024-02"],
            datasets=[ChartDatasetData(label="Alice", data=[10.0, 30.0, 20.0])]
        )

        # When
        result = VelocitySortUtils.sort_chart_data_chronologically(chart, ascending=False)

        # Then
        self.assertEqual(result.labels, ["2024-03", "2024-02", "2024-01"])
        self.assertEqual(result.datasets[0].data, [30.0, 20.0, 10.0])
