import json

from ..data.chart_data import ChartData


class ChartJsonUtils:

    @staticmethod
    def convert_chart_data_to_chartjs_json(chart_data: ChartData) -> str:
        if not chart_data or not chart_data.labels:
            return json.dumps({'labels': [], 'data': []})

        chart_dict = {
            'labels': chart_data.labels,
            'data': []
        }

        for dataset in chart_data.datasets:
            chart_dict['data'].append({
                'developer': dataset.label,
                'metrics': dataset.data
            })

        return json.dumps(chart_dict)

    @staticmethod
    def convert_chart_data_to_timeline_chartjs_json(chart_data: ChartData) -> str:
        if not chart_data or not chart_data.datasets:
            return json.dumps({'labels': [], 'datasets': []})

        chart_dict = {
            'labels': chart_data.labels or [],
            'datasets': [],
            'min_date': chart_data.min_date,
            'max_date': chart_data.max_date
        }

        for dataset in chart_data.datasets:
            chart_dict['datasets'].append({
                'label': dataset.label,
                'data': dataset.data,
                'done': dataset.is_done
            })

        return json.dumps(chart_dict)
