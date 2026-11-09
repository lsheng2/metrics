import unittest

from ui_web.data.chart_data import ChartData, ChartDatasetData
from ui_web.utils.chart_transform_utils import ChartTransformUtils


class TestChartTransformUtilsRollingAverage(unittest.TestCase):

    def test_shouldSmoothValuesWhenWindowOfThreeApplied(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar", "Apr", "May"],
            datasets=[ChartDatasetData(label="Alice", data=[3.0, 6.0, 9.0, 12.0, 15.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 3)

        # Then
        self.assertEqual(result.datasets[0].data, [3.0, 4.5, 6.0, 9.0, 12.0])

    def test_shouldPreserveNoneValuesWhenDataContainsGaps(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar", "Apr"],
            datasets=[ChartDatasetData(label="Alice", data=[4.0, None, 8.0, 12.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 3)

        # Then
        self.assertIsNone(result.datasets[0].data[1])

    def test_shouldSkipNoneValuesInWindowWhenCalculatingAverage(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[4.0, None, 8.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 3)

        # Then
        self.assertEqual(result.datasets[0].data[2], 6.0)

    def test_shouldReturnOriginalValueWhenWindowIsOne(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[3.0, 6.0, 9.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 1)

        # Then
        self.assertEqual(result.datasets[0].data, [3.0, 6.0, 9.0])

    def test_shouldSmoothMultipleDatasetsIndependently(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[
                ChartDatasetData(label="Alice", data=[2.0, 4.0, 6.0]),
                ChartDatasetData(label="Bob", data=[10.0, 20.0, 30.0])
            ]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 2)

        # Then
        self.assertEqual(result.datasets[0].data, [2.0, 3.0, 5.0])
        self.assertEqual(result.datasets[1].data, [10.0, 15.0, 25.0])

    def test_shouldPreserveLabelsWhenSmoothingApplied(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 2)

        # Then
        self.assertEqual(result.labels, ["Jan", "Feb", "Mar"])

    def test_shouldPreserveDatasetMetadataWhenSmoothingApplied(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 2)

        # Then
        self.assertEqual(result.datasets[0].label, "Alice")

    def test_shouldRoundAveragesToTwoDecimalPlaces(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 3)

        # Then
        self.assertEqual(result.datasets[0].data, [1.0, 1.5, 2.0])

    def test_shouldUsePartialWindowWhenFewerPrecedingValuesThanWindowSize(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar", "Apr"],
            datasets=[ChartDatasetData(label="Alice", data=[10.0, 20.0, 30.0, 40.0])]
        )

        # When
        result = ChartTransformUtils.apply_rolling_average(chart, 3)

        # Then
        self.assertEqual(result.datasets[0].data[0], 10.0)
        self.assertEqual(result.datasets[0].data[1], 15.0)
        self.assertEqual(result.datasets[0].data[2], 20.0)
        self.assertEqual(result.datasets[0].data[3], 30.0)


class TestChartTransformUtilsTrimToLastNPeriods(unittest.TestCase):

    def test_shouldTrimToLastThreePeriodsWhenChartHasMorePeriods(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar", "Apr", "May"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0, 4.0, 5.0])]
        )

        # When
        result = ChartTransformUtils.trim_to_last_n_periods(chart, 3)

        # Then
        self.assertEqual(result.labels, ["Mar", "Apr", "May"])
        self.assertEqual(result.datasets[0].data, [3.0, 4.0, 5.0])

    def test_shouldReturnAllDataWhenChartHasFewerPeriodsThanRequested(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0])]
        )

        # When
        result = ChartTransformUtils.trim_to_last_n_periods(chart, 5)

        # Then
        self.assertEqual(result.labels, ["Jan", "Feb"])
        self.assertEqual(result.datasets[0].data, [1.0, 2.0])

    def test_shouldReturnAllDataWhenChartHasExactlyNPeriods(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0])]
        )

        # When
        result = ChartTransformUtils.trim_to_last_n_periods(chart, 3)

        # Then
        self.assertEqual(result.labels, ["Jan", "Feb", "Mar"])
        self.assertEqual(result.datasets[0].data, [1.0, 2.0, 3.0])

    def test_shouldTrimMultipleDatasetsConsistently(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar", "Apr"],
            datasets=[
                ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0, 4.0]),
                ChartDatasetData(label="Bob", data=[10.0, 20.0, 30.0, 40.0])
            ]
        )

        # When
        result = ChartTransformUtils.trim_to_last_n_periods(chart, 2)

        # Then
        self.assertEqual(result.labels, ["Mar", "Apr"])
        self.assertEqual(result.datasets[0].data, [3.0, 4.0])
        self.assertEqual(result.datasets[1].data, [30.0, 40.0])

    def test_shouldPreserveDatasetMetadataWhenTrimming(self):
        # Given
        chart = ChartData(
            labels=["Jan", "Feb", "Mar"],
            datasets=[ChartDatasetData(label="Alice", data=[1.0, 2.0, 3.0])]
        )

        # When
        result = ChartTransformUtils.trim_to_last_n_periods(chart, 2)

        # Then
        self.assertEqual(result.datasets[0].label, "Alice")
