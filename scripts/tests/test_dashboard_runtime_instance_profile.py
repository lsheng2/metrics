from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from dashboard_runtime_instance_profile import (
    build_dashboard_runtime_instance_profile,
    load_or_create_dashboard_runtime_instance_profile,
    main,
    prioritize_profile_port,
    read_dashboard_runtime_instance_profile,
    render_dashboard_runtime_env_projection,
    write_dashboard_runtime_instance_profile,
)
from service_lifecycle_engine import ExternalServiceMode, detect_runtime_isolation_conflicts


def test_profile_generates_dashboard_runtime_projections_from_instance_id(tmp_path: Path) -> None:
    repo_root = tmp_path / "scrum_dashboard"
    workspace_root = tmp_path / "workspace"
    repo_root.mkdir()
    workspace_root.mkdir()

    profile = build_dashboard_runtime_instance_profile(
        repo_root=repo_root,
        workspace_root=workspace_root,
        port_profile="worktree-1",
    )

    assert profile.identity.project_name == "metrics-bug-trend"
    assert profile.identity.instance_id.startswith("worktree-1-")
    assert profile.service_ports["django"] == 8012
    assert profile.service_ports["grafana"] == 3051
    assert profile.lifecycle_instance_name == profile.identity.instance_id
    assert profile.service_lifecycle_state_dir == workspace_root.resolve() / "state" / "local" / "instances" / profile.identity.instance_id / "service-lifecycle-engine"
    assert profile.dashboard_namespace.key_prefix == f"metrics-bug-trend:{profile.identity.instance_id}:dashboard:"
    assert profile.django_namespace.ports == {"http": 8012}
    assert profile.grafana_namespace.ports == {"http": 3051}


def test_profile_dedicated_bindings_do_not_conflict_with_each_other(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    profile = build_dashboard_runtime_instance_profile(repo_root=workspace_root, workspace_root=workspace_root)

    conflicts = detect_runtime_isolation_conflicts(profile.dedicated_bindings)

    assert conflicts == ()
    assert {binding.mode for binding in profile.dedicated_bindings} == {ExternalServiceMode.DEDICATED}
    assert {binding.service_name for binding in profile.shared_consumed_bindings} == {"ai-base-backend", "ai-base-frontend", "external-litellm"}
    assert all(not binding.stop_decision(actor=profile.identity).allowed for binding in profile.shared_consumed_bindings)


def test_load_or_create_profile_reuses_durable_identity(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    profile_path = workspace_root / "state" / "local" / "runtime-instance.json"
    env_path = workspace_root / "state" / "local" / "worktree-runtime.env"
    workspace_root.mkdir()

    first = load_or_create_dashboard_runtime_instance_profile(
        workspace_root=workspace_root,
        profile_path=profile_path,
        env_path=env_path,
        port_profile="worktree-2",
    )
    second = load_or_create_dashboard_runtime_instance_profile(
        workspace_root=workspace_root,
        profile_path=profile_path,
        env_path=env_path,
    )

    assert second.identity == first.identity
    assert second.service_ports["django"] == 8022
    assert profile_path.exists()
    assert env_path.exists()
    assert f"METRICS_DASHBOARD_RUNTIME_INSTANCE_ID={first.identity.instance_id}" in env_path.read_text(encoding="utf-8")


def test_profile_round_trips_as_json(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    path = tmp_path / "runtime-instance.json"
    profile = build_dashboard_runtime_instance_profile(repo_root=workspace_root, workspace_root=workspace_root, port_profile="default")

    write_dashboard_runtime_instance_profile(path, profile)
    loaded = read_dashboard_runtime_instance_profile(path)

    assert loaded.identity == profile.identity
    assert loaded.workspace_root == profile.workspace_root
    assert loaded.service_ports == profile.service_ports
    assert loaded.service_lifecycle_state_dir == profile.service_lifecycle_state_dir


def test_worktree_runtime_env_is_projection_of_profile(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    profile = build_dashboard_runtime_instance_profile(repo_root=workspace_root, workspace_root=workspace_root, port_profile="worktree-3")

    projection = render_dashboard_runtime_env_projection(profile)

    assert f"METRICS_DASHBOARD_RUNTIME_INSTANCE_ID={profile.identity.instance_id}" in projection
    assert f"METRICS_SERVICE_LIFECYCLE_INSTANCE_NAME={profile.identity.instance_id}" in projection
    assert "METRICS_DASHBOARD_PORT_PROFILE=worktree-3" in projection
    assert "METRICS_DJANGO_PORT=8032" in projection
    assert "METRICS_GRAFANA_PORT=3251" in projection
    assert f"METRICS_DASHBOARD_SERVICE_LIFECYCLE_STATE_DIR={profile.service_lifecycle_state_dir}" in projection
    assert "DASHBOARD_METRICS_BASE_URL=http://127.0.0.1:8032" in projection
    assert "METRICS_EXTERNAL_LITELLM_URL=http://127.0.0.1:4000" in projection


def test_profile_cli_writes_profile_and_projection(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    profile_path = workspace_root / "state" / "local" / "runtime-instance.json"
    env_path = workspace_root / "state" / "local" / "worktree-runtime.env"
    workspace_root.mkdir()

    exit_code = main(
        [
            "write",
            "--repo-root",
            str(workspace_root),
            "--workspace-root",
            str(workspace_root),
            "--port-profile",
            "worktree-4",
            "--profile-path",
            str(profile_path),
            "--env-path",
            str(env_path),
        ]
    )

    assert exit_code == 0
    profile = read_dashboard_runtime_instance_profile(profile_path)
    assert profile.identity.instance_id.startswith("worktree-4-")
    assert profile.service_ports["django"] == 8042
    assert "METRICS_GRAFANA_PORT=3351" in env_path.read_text(encoding="utf-8")


def test_profile_port_is_prioritized_without_dropping_fallbacks(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    profile = build_dashboard_runtime_instance_profile(repo_root=workspace_root, workspace_root=workspace_root, port_profile="worktree-1")

    ports = prioritize_profile_port((8002, 8012, 8022), profile, "django")

    assert ports == (8012, 8002, 8022)
