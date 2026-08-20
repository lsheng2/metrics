import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand

from bug_metrics.container import bug_metrics_container
from bug_metrics.models import BugTrendCalculationRun


class Command(BaseCommand):
    help = 'Export a run-pinned Bug Trend chart fixture for Grafana parity checks.'

    def add_arguments(self, parser):
        parser.add_argument('--scope', type=int, required=True)
        parser.add_argument('--run', required=True)
        parser.add_argument('--begin', default='')
        parser.add_argument('--end', default='')
        parser.add_argument('--output', default='state/grafana_bug_trend_fixture.json')

    def handle(self, *args, **options):
        run = BugTrendCalculationRun.objects.select_related('scope').get(id=options['run'], scope_id=options['scope'])
        begin = date.fromisoformat(options['begin']) if options['begin'] else run.source_coverage_start
        end = date.fromisoformat(options['end']) if options['end'] else run.source_coverage_end
        chart = bug_metrics_container.bug_trend_api.get_chart_for_run(str(run.id), begin, end)
        payload = {
            'scope_id': chart.scope_id,
            'calculation_run_id': chart.calculation_run_id,
            'begin': begin.isoformat(),
            'end': end.isoformat(),
            'labels': chart.labels,
            'bucket_ids': chart.bucket_ids,
            'datasets': [
                {
                    'series_name': dataset.series_name,
                    'type': dataset.chart_type,
                    'values': dataset.values,
                    'color': dataset.color,
                }
                for dataset in chart.datasets
            ],
            'unavailable_reason': chart.unavailable_reason,
        }
        output_path = Path(options['output'])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Exported Grafana bug trend fixture to {output_path}'))