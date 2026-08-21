from django.db import migrations


DEFAULT_BUG_TREND_CHART_SPEC = {
    'evidence_contract_id': 'default_bug_trend_bucket_series',
    'series': [
        'all_open_bugs',
        'new_critical_high',
        'new_medium_low',
        'fixed_or_closed_bugs',
        'all_open_critical_high',
    ],
}


def populate_default_chart_spec(apps, schema_editor):
    chart_definition_model = apps.get_model('bug_metrics', 'BugTrendChartDefinition')
    chart_definition_model.objects.filter(
        chart_id='default_bug_trend',
        chart_spec={},
    ).update(chart_spec=DEFAULT_BUG_TREND_CHART_SPEC)


def clear_default_chart_spec(apps, schema_editor):
    chart_definition_model = apps.get_model('bug_metrics', 'BugTrendChartDefinition')
    chart_definition_model.objects.filter(
        chart_id='default_bug_trend',
        chart_spec=DEFAULT_BUG_TREND_CHART_SPEC,
    ).update(chart_spec={})


class Migration(migrations.Migration):

    dependencies = [
        ('bug_metrics', '0007_chart_definition_spec'),
    ]

    operations = [
        migrations.RunPython(populate_default_chart_spec, clear_default_chart_spec),
    ]
