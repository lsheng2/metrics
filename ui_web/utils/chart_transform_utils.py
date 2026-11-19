from ..data.chart_data import ChartData, ChartDatasetData


class ChartTransformUtils:

    @staticmethod
    def apply_rolling_average(chart: ChartData, window: int) -> ChartData:
        new_datasets = []
        for dataset in chart.datasets:
            smoothed_data = []
            for i, value in enumerate(dataset.data):
                if value is None:
                    smoothed_data.append(None)
                else:
                    start = max(0, i - window + 1)
                    window_values = [v for v in dataset.data[start:i + 1] if v is not None]
                    avg = sum(window_values) / len(window_values) if window_values else None
                    smoothed_data.append(round(avg, 2) if avg else None)
            new_datasets.append(ChartDatasetData(
                label=dataset.label,
                data=smoothed_data
            ))
        return ChartData(labels=chart.labels, datasets=new_datasets)

    @staticmethod
    def trim_to_last_n_periods(chart: ChartData, n: int) -> ChartData:
        trimmed_labels = chart.labels[-n:] if len(chart.labels) > n else chart.labels
        trimmed_datasets = []
        for dataset in chart.datasets:
            trimmed_data = dataset.data[-n:] if len(dataset.data) > n else dataset.data
            trimmed_datasets.append(ChartDatasetData(
                label=dataset.label,
                data=trimmed_data
            ))
        return ChartData(labels=trimmed_labels, datasets=trimmed_datasets)
