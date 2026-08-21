import pytest

from scripts.compare_grafana_bug_trend_parity import chart_id_from, chart_target_from


def test_shouldReadChartIdFromGrafanaArtifactTarget():
    artifact = {
        'panels': [
            {
                'targets': [
                    {'path': '/api/bug-trend/chart-data/?scope_id=$scope_id&begin=$begin&end=$end&chart_id=ai_open_only'}
                ]
            }
        ]
    }

    chart_target = chart_target_from(artifact)

    assert chart_id_from(chart_target) == 'ai_open_only'


def test_shouldRejectGrafanaArtifactTargetWhenRequiredChartIdIsOmitted():
    artifact = {
        'panels': [
            {
                'targets': [
                    {'path': '/api/bug-trend/chart-data/?scope_id=$scope_id&begin=$begin&end=$end'}
                ]
            }
        ]
    }

    chart_target = chart_target_from(artifact)

    with pytest.raises(SystemExit, match='FAIL chart-data target must declare chart_id'):
        chart_id_from(chart_target)
