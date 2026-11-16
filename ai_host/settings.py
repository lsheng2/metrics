from pathlib import Path

from django.conf import settings as django_settings

from ai_base_runtime import RuntimeLimits, RuntimeSettings, request_body_policy
from ai_base_runtime.spi import (
    HostConfig,
    HttpLimits,
    LifecycleLimits,
    ModelConfig,
    NetworkPolicy,
    PROVIDER_OPENAI_COMPATIBLE,
)
from pydantic import SecretStr

from metrics.auth import BASIC_AUTH_CHALLENGE


APP_ID = 'metrics'
SERVER_THREADS = 14
HTTP_MAX_STREAMS = 4
HTTP_MAX_REQUESTS = 4
PAGE_THREAD_RESERVE = 6
AI_PANE_TIMEOUT_SECONDS = 1.0
AI_PANE_CONCURRENCY_LIMIT = 2
HEARTBEAT_INTERVAL_SECONDS = 2.0
HTTP_CLOSE_TIMEOUT_SECONDS = 2.0
RUNTIME_STOP_TIMEOUT_SECONDS = 1.0
RUNTIME_START_SECONDS = 20.0
RUNTIME_LIMIT_VALUES = (4, 60, 65_536, 65_536, 16_384)
MODEL_SETTING_NAMES = (
    'METRICS_AI_MODEL_BASE_URL',
    'METRICS_AI_MODEL_NAME',
    'METRICS_AI_MODEL_API_KEY',
)


def runtime_mount_path(base_url=None):
    raw_base = django_settings.METRICS_BASE_URL if base_url is None else base_url
    normalized = str(raw_base or '').strip('/')
    if not normalized:
        return '/ai'
    return f'/{normalized}/ai'


def missing_model_settings():
    missing = []
    for name in MODEL_SETTING_NAMES:
        value = getattr(django_settings, name, '')
        if not str(value or '').strip():
            missing.append(name)
    return tuple(missing)


def build_runtime_settings():
    return RuntimeSettings(
        limits=RuntimeLimits(
            max_concurrent_runs=RUNTIME_LIMIT_VALUES[0],
            max_tool_duration_seconds=RUNTIME_LIMIT_VALUES[1],
            max_captured_output_bytes=RUNTIME_LIMIT_VALUES[2],
            max_input_tokens=RUNTIME_LIMIT_VALUES[3],
            max_output_tokens=RUNTIME_LIMIT_VALUES[4],
        ),
    )


def body_limit_for_waitress(apps):
    return request_body_policy(build_runtime_settings(), apps).max_request_body_bytes + 1


def build_host_config():
    return HostConfig(
        state_dir=Path(django_settings.METRICS_STATE_DIR) / 'ai-base',
        allowed_hosts=tuple(django_settings.ALLOWED_HOSTS),
        lifecycle=LifecycleLimits(
            stop_timeout_seconds=RUNTIME_STOP_TIMEOUT_SECONDS,
            heartbeat_interval_seconds=HEARTBEAT_INTERVAL_SECONDS,
            http_close_timeout_seconds=HTTP_CLOSE_TIMEOUT_SECONDS,
        ),
        root_path=runtime_mount_path(),
        http_limits=HttpLimits(max_streams=HTTP_MAX_STREAMS, max_requests=HTTP_MAX_REQUESTS),
        model=_build_model_config(),
        network=NetworkPolicy(),
        www_authenticate=BASIC_AUTH_CHALLENGE,
        allow_anonymous_approval=bool(getattr(django_settings, 'AI_HOST_ALLOW_ANONYMOUS_APPROVAL', False)),
    )


def _build_model_config():
    if missing_model_settings():
        return None
    return ModelConfig(
        provider=PROVIDER_OPENAI_COMPATIBLE,
        name=django_settings.METRICS_AI_MODEL_NAME,
        base_url=django_settings.METRICS_AI_MODEL_BASE_URL,
        api_key=SecretStr(django_settings.METRICS_AI_MODEL_API_KEY),
    )
