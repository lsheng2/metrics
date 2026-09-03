from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import LiveServiceResolutionSource, LiveServiceResolver


def test_shouldResolveExplicitServiceEndpointBeforeOtherSources():
    resolver = LiveServiceResolver(
        lifecycle_state={"api": {"host": "127.0.0.1", "port": 8100}},
        default_ports={"api": 8000},
    )

    resolution = resolver.resolve("api", explicit_base_url="http://localhost:9000")

    assert resolution.base_url == "http://localhost:9000"
    assert resolution.source == LiveServiceResolutionSource.EXPLICIT


def test_shouldResolveLifecycleStateBeforeProjectionAndDefaults():
    resolver = LiveServiceResolver(
        lifecycle_state={"api": {"host": "127.0.0.1", "port": 8100}},
        projection={"api": {"host": "127.0.0.1", "port": 8200}},
        default_ports={"api": 8000},
    )

    resolution = resolver.resolve("api")

    assert resolution.base_url == "http://127.0.0.1:8100"
    assert resolution.source == LiveServiceResolutionSource.LIFECYCLE_STATE


def test_shouldResolveProjectionBeforeDefaultWhenLifecycleStateIsMissing():
    resolver = LiveServiceResolver(
        projection={"api": {"host": "127.0.0.1", "port": 8200}},
        default_ports={"api": 8000},
    )

    resolution = resolver.resolve("api")

    assert resolution.base_url == "http://127.0.0.1:8200"
    assert resolution.source == LiveServiceResolutionSource.PROJECT_PROJECTION


def test_shouldIgnoreProjectionWhenProjectionIsDisabled():
    resolver = LiveServiceResolver(
        projection={"api": {"host": "127.0.0.1", "port": 8200}},
        default_ports={"api": 8000},
        projection_enabled=False,
    )

    resolution = resolver.resolve("api")

    assert resolution.base_url == "http://127.0.0.1:8000"
    assert resolution.source == LiveServiceResolutionSource.DEFAULT


def test_shouldReportDiagnosticWhenDefaultFallbackIsUsed():
    resolver = LiveServiceResolver(default_ports={"api": 8000})

    resolution = resolver.resolve("api")

    assert resolution.diagnostics == ("default_port_fallback",)


def test_shouldNotUseLaunchAuthorityDiagnosticsAsEndpointTruthByDefault(tmp_path):
    authority_path = tmp_path / "launch-authority" / "api.json"
    authority_path.parent.mkdir()
    authority_path.write_text(json.dumps({"service": "api", "host": "127.0.0.1", "port": 9000}), encoding="utf-8")
    resolver = LiveServiceResolver(default_ports={"api": 8000}, diagnostics_authority_directory=authority_path.parent)

    resolution = resolver.resolve("api")

    assert resolution.base_url == "http://127.0.0.1:8000"
    assert resolution.source == LiveServiceResolutionSource.DEFAULT
