"""Deferred performance lane; invoke explicitly after functional acceptance."""
import json
from types import SimpleNamespace
import time

import pytest

from ai_host.tests.conformance_runtime_cases import asset_path, host_probe
from scripts.tests.windows_performance_support import performance_measurement_payload, performance_transport_payload


def validate_native_transport_payload(raw, server):
    from scripts.validation.windows_host_transport import validate_transport

    return validate_transport(
        raw, spacing_events=50, require_direct_asset=True,
        direct_asset_prefix=server.root_path + '/assets/',
    )


def test_native_transport_validation_binds_runtime_asset_prefix():
    raw = performance_measurement_payload()
    raw.update(performance_transport_payload(asset_prefix='/metrics/ai/assets/'))

    observed = validate_native_transport_payload(raw, SimpleNamespace(root_path='/metrics/ai'))

    assert observed['direct_asset_probes'] >= 1
    with pytest.raises(ValueError):
        validate_native_transport_payload(raw, SimpleNamespace(root_path='/wrong/ai'))


def test_native_transport_probe_observes_real_stream_spacing_and_saturation(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials, tmp_path,
):
    from ai_host.tests.conformance_fixtures import PASSWORD
    from scripts.validation.windows_host_transport import measure_spacing, saturated_streams

    auth = (ai_credentials.owner.id, PASSWORD)
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits, spacing_events=50) as (_, _, server):
        prefix = server.root_path + '/apps/qualification/api/qualification'
        asset = asset_path(server, ai_credentials)
        spacing = measure_spacing(server.base_url, probe_path=prefix, auth=auth)
        with saturated_streams(server.base_url, probe_path=prefix, auth=auth, direct_asset_path=asset) as saturated:
            time.sleep(1.2)
        raw = {'spacing': spacing, 'saturation': saturated}
        (tmp_path / 'transport.json').write_text(json.dumps(raw, indent=2), encoding='utf-8')
        observed = validate_native_transport_payload(raw, server)
        assert observed['short_probes'] >= 1 and observed['direct_asset_probes'] >= 1
