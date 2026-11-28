from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from django.core.exceptions import ImproperlyConfigured
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


MODEL_SETTINGS = {
    'METRICS_AI_MODEL_BASE_URL': 'https://model.example.internal/v1',
    'METRICS_AI_MODEL_NAME': 'gpt-test',
    'METRICS_AI_MODEL_API_KEY': 'synthetic-secret',
}


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


def test_explicit_model_ca_bundle_reaches_network_policy_and_keeps_tls_verification():
    import certifi

    ca_bundle = Path(certifi.where()).resolve()

    with override_settings(**MODEL_SETTINGS, METRICS_AI_MODEL_CA_BUNDLE=str(ca_bundle)):
        host_config = build_host_config()

    assert host_config.network.ca_bundle == ca_bundle
    assert host_config.network.verify_tls is True
    assert host_config.network.proxy_url is None


def test_empty_model_ca_bundle_keeps_default_trust_and_model_optionality():
    with override_settings(
        METRICS_AI_MODEL_BASE_URL='',
        METRICS_AI_MODEL_NAME='',
        METRICS_AI_MODEL_API_KEY='',
        METRICS_AI_MODEL_CA_BUNDLE='',
    ):
        host_config = build_host_config()

        assert missing_model_settings() == (
            'METRICS_AI_MODEL_BASE_URL',
            'METRICS_AI_MODEL_NAME',
            'METRICS_AI_MODEL_API_KEY',
        )
        assert host_config.model is None
        assert host_config.network.ca_bundle is None
        assert host_config.network.verify_tls is True
        assert host_config.network.proxy_url is None


@pytest.mark.parametrize(
    'bundle_factory',
    [
        pytest.param(lambda tmp_path: tmp_path / 'missing-ca.pem', id='missing'),
        pytest.param(lambda tmp_path: tmp_path, id='directory'),
    ],
)
def test_explicit_model_ca_bundle_fails_closed_when_path_is_not_a_readable_file(tmp_path, bundle_factory):
    ca_bundle = bundle_factory(tmp_path)

    with override_settings(**MODEL_SETTINGS, METRICS_AI_MODEL_CA_BUNDLE=str(ca_bundle)):
        with pytest.raises(ImproperlyConfigured) as raised:
            build_host_config()

    assert 'METRICS_AI_MODEL_CA_BUNDLE' in str(raised.value)
    assert str(ca_bundle) not in str(raised.value)


def test_explicit_model_ca_bundle_fails_closed_when_file_is_unreadable(tmp_path, monkeypatch):
    ca_bundle = tmp_path / 'unreadable-ca.pem'
    ca_bundle.write_text('-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n', encoding='utf-8')
    original_open = Path.open

    def deny_ca_read(self, *args, **kwargs):
        if self == ca_bundle.resolve():
            raise PermissionError(str(ca_bundle))
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'open', deny_ca_read)

    with override_settings(**MODEL_SETTINGS, METRICS_AI_MODEL_CA_BUNDLE=str(ca_bundle)):
        with pytest.raises(ImproperlyConfigured) as raised:
            build_host_config()

    assert 'METRICS_AI_MODEL_CA_BUNDLE' in str(raised.value)
    assert str(ca_bundle) not in str(raised.value)


def test_explicit_model_ca_bundle_fails_closed_when_pem_is_invalid(tmp_path):
    ca_bundle = tmp_path / 'invalid-ca.pem'
    ca_bundle.write_text('not a pem certificate bundle', encoding='utf-8')

    with override_settings(**MODEL_SETTINGS, METRICS_AI_MODEL_CA_BUNDLE=str(ca_bundle)):
        with pytest.raises(ImproperlyConfigured) as raised:
            build_host_config()

    assert 'METRICS_AI_MODEL_CA_BUNDLE' in str(raised.value)
    assert str(ca_bundle) not in str(raised.value)


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
