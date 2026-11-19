from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from django.test import SimpleTestCase, override_settings

from ai_host.settings import (
    HTTP_MAX_REQUESTS,
    HTTP_MAX_STREAMS,
    PAGE_THREAD_RESERVE,
    RUNTIME_LIMIT_VALUES,
    SERVER_THREADS,
    body_limit_for_waitress,
    build_host_config,
    build_runtime_settings,
    missing_model_settings,
    runtime_mount_path,
)
from ai_host.package import METRICS_APP


@pytest.mark.parametrize(('runtime_cap', 'expected'), [(512, 1_048_577), (16_777_216, 16_777_217)])
def test_body_cap_uses_the_selected_settings_and_keeps_the_larger_app_limit(monkeypatch, runtime_cap, expected):
    selected = build_runtime_settings()

    def policy(settings, apps):
        assert settings is selected
        assert apps == (METRICS_APP,)
        return SimpleNamespace(max_request_body_bytes=runtime_cap)

    def unexpected_rebuild():
        pytest.fail('body policy must use the same settings passed to start_blocking')

    monkeypatch.setattr('ai_base_runtime.request_body_policy', policy)
    monkeypatch.setattr('ai_host.settings.build_runtime_settings', unexpected_rebuild)
    assert body_limit_for_waitress(selected, (METRICS_APP,)) == expected


class TestAiHostSettings(SimpleTestCase):
    def test_shouldUseTheMeasuredConfiguredModelStartupBudget(self):
        from ai_host.settings import RUNTIME_START_SECONDS

        root = Path(__file__).resolve().parents[2]
        evidence = json.loads((root / (
            'openspec/changes/embed-ai-base-runtime-in-process/evidence/'
            'configured-startup-20261116.json'
        )).read_text(encoding='utf-8'))
        observed = [evidence['profileRunStartupSeconds'], *evidence['emptyStartupSeconds'],
                    *evidence['populatedStartupSeconds']]
        assert len(observed) == 11
        assert RUNTIME_START_SECONDS == evidence['selectedStartTimeoutSeconds']
        assert RUNTIME_START_SECONDS > max(observed)

    def test_shouldBuildRuntimeSettingsWithoutReadingModelConfiguration(self):
        runtime_settings = build_runtime_settings()

        assert (
            runtime_settings.limits.max_concurrent_runs,
            runtime_settings.limits.max_tool_duration_seconds,
            runtime_settings.limits.max_captured_output_bytes,
            runtime_settings.limits.max_input_tokens,
            runtime_settings.limits.max_output_tokens,
        ) == RUNTIME_LIMIT_VALUES
        assert runtime_settings.request_body_limits.default == 1_048_576
        assert body_limit_for_waitress(runtime_settings, (METRICS_APP,)) == 8_388_609

    @override_settings(METRICS_BASE_URL='', METRICS_STATE_DIR=Path('C:/tmp/metrics-state'))
    def test_shouldMountRuntimeAtAiWhenBaseUrlIsEmpty(self):
        host_config = build_host_config()

        assert runtime_mount_path() == '/ai'
        assert host_config.root_path == '/ai'
        assert host_config.state_dir == Path('C:/tmp/metrics-state') / 'ai-base'

    @override_settings(METRICS_BASE_URL='/metrics/')
    def test_shouldMountRuntimeUnderConfiguredBaseUrl(self):
        assert runtime_mount_path() == '/metrics/ai'

    @override_settings(
        ALLOWED_HOSTS=['127.0.0.1', 'metrics.example.internal'],
        METRICS_AI_MODEL_BASE_URL='https://model.example.internal/v1',
        METRICS_AI_MODEL_NAME='gpt-test',
        METRICS_AI_MODEL_API_KEY='synthetic-secret',
    )
    def test_shouldBuildHostConfigWithCommonAllowedHostsAndConfiguredModel(self):
        host_config = build_host_config()

        assert host_config.allowed_hosts == ('127.0.0.1', 'metrics.example.internal')
        assert host_config.model is not None
        assert host_config.model.provider == 'openai-compatible'
        assert host_config.model.name == 'gpt-test'
        assert host_config.model.base_url == 'https://model.example.internal/v1'
        assert 'synthetic-secret' not in repr(host_config)

    @override_settings(
        METRICS_AI_MODEL_BASE_URL='https://model.example.internal/v1',
        METRICS_AI_MODEL_NAME='',
        METRICS_AI_MODEL_API_KEY='',
    )
    def test_shouldReportMissingModelVariablesWithoutValues(self):
        host_config = build_host_config()

        assert host_config.model is None
        assert missing_model_settings() == ('METRICS_AI_MODEL_NAME', 'METRICS_AI_MODEL_API_KEY')

    def test_shouldReservePageThreadsOutsideAiLimits(self):
        assert SERVER_THREADS - HTTP_MAX_STREAMS - HTTP_MAX_REQUESTS >= PAGE_THREAD_RESERVE

    @override_settings(AI_HOST_ALLOW_ANONYMOUS_APPROVAL=True)
    def test_shouldUseSingleSettingsAuthorityForDevelopmentAnonymousApproval(self):
        assert build_host_config().allow_anonymous_approval is True
