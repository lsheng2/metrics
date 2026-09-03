from __future__ import annotations

import os
from pathlib import Path

INFINITY_DATASOURCE_PLUGIN_ID = "yesoreyeram-infinity-datasource"


def write_runtime_grafana_config(workspace: Path, grafana_port: int) -> Path:
    source = workspace / "state" / "grafana" / "grafana.ini"
    ensure_grafana_state_directories(workspace)
    runtime_directory = workspace / "state" / "grafana" / "runtime"
    runtime_directory.mkdir(parents=True, exist_ok=True)
    target = runtime_directory / f"grafana-e2e-{grafana_port}.ini"
    content = source.read_text(encoding="utf-8") if source.exists() else default_grafana_config_content(workspace, grafana_port)
    lines = []
    for line in content.splitlines():
        if line.strip().startswith("http_port"):
            lines.append(f"http_port = {grafana_port}")
        elif line.strip().startswith("root_url"):
            lines.append(f"root_url = http://127.0.0.1:{grafana_port}/")
        else:
            lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def ensure_grafana_state_directories(workspace: Path) -> None:
    grafana_state = workspace / "state" / "grafana"
    for directory in (
        grafana_state / "data",
        grafana_state / "data" / "plugins",
        grafana_state / "logs",
        grafana_state / "conf" / "provisioning",
        grafana_state / "conf" / "provisioning" / "alerting",
        grafana_state / "conf" / "provisioning" / "dashboards",
        grafana_state / "conf" / "provisioning" / "datasources",
        grafana_state / "conf" / "provisioning" / "plugins",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def default_grafana_config_content(workspace: Path, grafana_port: int) -> str:
    grafana_state = workspace / "state" / "grafana"
    plugins_path = resolve_grafana_plugins_path(workspace)
    return "\n".join([
        "[server]",
        "http_addr = 127.0.0.1",
        f"http_port = {grafana_port}",
        "domain = localhost",
        f"root_url = http://127.0.0.1:{grafana_port}/",
        "",
        "[paths]",
        f"data = {(grafana_state / 'data').as_posix()}",
        f"logs = {(grafana_state / 'logs').as_posix()}",
        f"plugins = {plugins_path.as_posix()}",
        f"provisioning = {(grafana_state / 'conf' / 'provisioning').as_posix()}",
        "",
        "[security]",
        "admin_user = admin",
        "admin_password = admin",
        "allow_embedding = true",
        "",
        "[auth.anonymous]",
        "enabled = true",
        "org_role = Admin",
        "",
        "[plugins]",
        "allow_loading_unsigned_plugins = yesoreyeram-infinity-datasource",
        "preinstall_disabled = true",
        "check_for_plugin_updates = false",
    ])


def resolve_grafana_plugins_path(workspace: Path) -> Path:
    configured = os.environ.get("GRAFANA_PLUGINS_PATH") or os.environ.get("GF_PATHS_PLUGINS")
    if configured:
        return Path(configured).resolve()
    local_plugins = workspace / "state" / "grafana" / "data" / "plugins"
    if (local_plugins / INFINITY_DATASOURCE_PLUGIN_ID).exists():
        return local_plugins
    shared_plugins = shared_worktree_grafana_plugins_path(workspace)
    if shared_plugins and (shared_plugins / INFINITY_DATASOURCE_PLUGIN_ID).exists():
        return shared_plugins
    return local_plugins


def shared_worktree_grafana_plugins_path(workspace: Path) -> Path | None:
    if workspace.parent.name != ".worktrees":
        return None
    return workspace.parent.parent / "state" / "grafana" / "data" / "plugins"
