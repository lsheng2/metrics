from ai_base_runtime.testkit import check_app_package

from ai_host.package import METRICS_APP
from ai_host.settings import build_runtime_settings


def test_metrics_package_declares_workbench_context_and_ui_only_actions():
    check_app_package(METRICS_APP, limits=build_runtime_settings().limits)
    assert {provider.kind for provider in METRICS_APP.context_providers} == {'metrics.workbench'}
    assert {action.name for action in METRICS_APP.host_actions} == {'metrics.openChart', 'metrics.openEvidence'}
