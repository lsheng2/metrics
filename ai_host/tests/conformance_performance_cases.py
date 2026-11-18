"""Deferred performance lane; invoke explicitly after functional acceptance."""
import json
import time

from ai_host.tests.conformance_runtime_cases import host_probe


def test_native_transport_probe_observes_real_stream_spacing_and_saturation(
    ai_host_mode, ai_host_factory, ai_server_factory, ai_clock_and_limits, ai_credentials, tmp_path,
):
    from ai_host.tests.conformance_fixtures import PASSWORD
    from scripts.validation.windows_host_transport import measure_spacing, saturated_streams, validate_transport

    auth = (ai_credentials.owner.id, PASSWORD)
    with host_probe(ai_host_factory, ai_server_factory, ai_clock_and_limits) as (_, _, server):
        prefix = server.root_path + '/apps/qualification/api/qualification'
        spacing = measure_spacing(server.base_url, probe_path=prefix, auth=auth)
        with saturated_streams(server.base_url, probe_path=prefix, auth=auth) as saturated:
            time.sleep(1.2)
        raw = {'spacing': spacing, 'saturation': saturated}
        (tmp_path / 'transport.json').write_text(json.dumps(raw, indent=2), encoding='utf-8')
        observed = validate_transport(raw)
        assert observed['short_probes'] >= 1 and observed['excess_probes'] >= 1
