from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from service_lifecycle_engine import (
    PlatformOperationSet,
    ProvenanceCapability,
    capture_process_provenance,
    provenance_capability_for,
    resolve_owned_listener,
)


def test_shouldResolveOwnedListenerWhenWrapperAndListenerShareProcessGroup():
    operations = PlatformOperationSet(
        get_listening_process_ids=lambda host, port: (222, 333),
        process_group_id=lambda pid: 7 if pid in {111, 222} else 8,
    )

    assert resolve_owned_listener(operations, "127.0.0.1", 8100, 111) == 222


def test_shouldCaptureWrapperOnlyProvenanceWhenNoStrongEvidenceExists():
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: False,
        get_listening_process_ids=lambda host, port: (),
        process_start_marker=lambda pid: "started:111",
    )

    provenance = capture_process_provenance(operations, 111, ("python", "api.py"), "127.0.0.1", 8100)

    assert provenance.wrapper_pid == 111
    assert provenance.listener_pid is None
    assert provenance.process_start_marker == "started:111"
    assert provenance.capability == ProvenanceCapability.WRAPPER_ONLY


def test_shouldCaptureHttpIdentityAsHighestAvailableCapability():
    operations = PlatformOperationSet(
        process_exists=lambda pid: True,
        process_matches_command=lambda pid, command: True,
        get_listening_process_ids=lambda host, port: (222,),
        process_group_id=lambda pid: 7 if pid in {111, 222} else None,
        process_start_marker=lambda pid: f"started:{pid}",
        http_status_ok=lambda url: True,
        http_probe=lambda url: {"body_sha256": "identity-sha"},
    )

    provenance = capture_process_provenance(
        operations,
        111,
        ("python", "api.py"),
        "127.0.0.1",
        8100,
        health_url="http://127.0.0.1:8100/health",
        listener_identity_url="http://127.0.0.1:8100/identity",
    )

    assert provenance.listener_pid == 222
    assert provenance.process_group_id == 7
    assert provenance.listener_identity_fingerprint == "identity-sha"
    assert provenance.capability == ProvenanceCapability.HTTP_IDENTITY


def test_shouldCaptureSingleEndpointListenerWhenWrapperAlreadyExited():
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid == 222,
        process_matches_command=lambda pid, command: False,
        get_listening_process_ids=lambda host, port: (222,),
        process_start_marker=lambda pid: "",
        http_status_ok=lambda url: True,
    )

    provenance = capture_process_provenance(
        operations,
        111,
        ("python", "api.py"),
        "127.0.0.1",
        8100,
        health_url="http://127.0.0.1:8100/health",
    )

    assert provenance.wrapper_pid == 111
    assert provenance.listener_pid == 222
    assert provenance.capability == ProvenanceCapability.ENDPOINT_GRADE


def test_shouldCaptureSingleEndpointListenerWhenWrapperIsNotTheListener():
    operations = PlatformOperationSet(
        process_exists=lambda pid: pid in {111, 222},
        process_matches_command=lambda pid, command: pid == 111,
        get_listening_process_ids=lambda host, port: (222,),
        process_start_marker=lambda pid: f"started:{pid}",
        http_status_ok=lambda url: True,
    )

    provenance = capture_process_provenance(
        operations,
        111,
        ("python", "api.py"),
        "127.0.0.1",
        8100,
        health_url="http://127.0.0.1:8100/health",
    )

    assert provenance.wrapper_pid == 111
    assert provenance.listener_pid == 222
    assert provenance.capability == ProvenanceCapability.ENDPOINT_GRADE


def test_shouldNotTreatHttpIdentityAsOwnedListenerProofByItself():
    capability = provenance_capability_for(
        wrapper_pid=111,
        command_matches=True,
        listener_pid=None,
        endpoint_reachable=True,
        listener_identity_fingerprint="identity-sha",
    )

    assert capability == ProvenanceCapability.REGISTERED_PROCESS


def test_shouldTreatListenerWithoutWrapperAsWrapperOnlyEvidence():
    capability = provenance_capability_for(
        wrapper_pid=None,
        command_matches=False,
        listener_pid=222,
        endpoint_reachable=True,
        listener_identity_fingerprint="identity-sha",
    )

    assert capability == ProvenanceCapability.WRAPPER_ONLY


def test_shouldClassifyEndpointGradeWithoutTreatingItAsHttpIdentity():
    capability = provenance_capability_for(
        wrapper_pid=111,
        command_matches=True,
        listener_pid=222,
        endpoint_reachable=True,
        listener_identity_fingerprint=None,
    )

    assert capability == ProvenanceCapability.ENDPOINT_GRADE
